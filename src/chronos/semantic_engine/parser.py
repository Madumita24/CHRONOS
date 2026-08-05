"""SQLGlot-backed deterministic single-model parser."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from .errors import SqlParseError
from .models import (
    SQL_PARSER_NAME,
    SQL_PARSER_VERSION,
    AggregationContract,
    ColumnReference,
    JoinContract,
    OutputColumnContract,
    ParsedModel,
    RelationContract,
)
from .serialization import semantic_fingerprint


_OPERATORS = (
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
    exp.Mod,
    exp.EQ,
    exp.NEQ,
    exp.GT,
    exp.GTE,
    exp.LT,
    exp.LTE,
    exp.And,
    exp.Or,
    exp.Not,
    exp.In,
    exp.Like,
    exp.ILike,
    exp.Between,
)


def parse_model(sql: str, *, dialect: str) -> ParsedModel:
    if not isinstance(sql, str) or not sql.strip():
        raise SqlParseError("SQL input must be non-empty text.")
    if sqlglot.__version__ != SQL_PARSER_VERSION:
        raise SqlParseError(
            f"SQL parser version mismatch: expected {SQL_PARSER_VERSION}, observed {sqlglot.__version__}."
        )
    try:
        statements = [item for item in sqlglot.parse(sql, read=dialect) if item is not None]
    except (ParseError, ValueError) as exc:
        raise SqlParseError(f"SQL parsing failed for dialect {dialect!r}.") from exc
    if len(statements) != 1:
        raise SqlParseError("Exactly one top-level SQL statement is supported.")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise SqlParseError("Phase 6.2 supports exactly one SELECT model.")
    if any(isinstance(item, (exp.Command, exp.Execute)) for item in tree.walk()):
        raise SqlParseError("Dynamic or executable SQL is unsupported.")

    tree = tree.transform(
        lambda item: item.this if isinstance(item, exp.Paren) else item,
        copy=False,
    )
    _normalize_effective_alias_quotes(tree)
    canonical = _sql(tree, dialect)
    cte_names = tuple(
        sorted(
            {
                item.alias_or_name.lower()
                for item in tree.find_all(exp.CTE)
                if item.alias_or_name
            }
        )
    )
    relations = _relations(tree, cte_names, dialect)
    outputs = tuple(
        _output_contract(item, ordinal=index, dialect=dialect)
        for index, item in enumerate(tree.expressions)
    )
    output_names = [item.output_name.lower() for item in outputs]
    if len(output_names) != len(set(output_names)):
        raise SqlParseError("Output aliases must be unique under normalized identity.")
    where = tree.args.get("where")
    grouping = tree.args.get("group")
    ordering = tree.args.get("order")
    windows = tuple(
        sorted({_sql(item, dialect) for item in tree.find_all(exp.Window)})
    )
    unresolved_stars = tuple(
        sorted({_sql(item, dialect) for item in tree.find_all(exp.Star)})
    )
    parsed = ParsedModel(
        statement_type="SELECT",
        dialect=dialect.lower(),
        parser_name=SQL_PARSER_NAME,
        parser_version=SQL_PARSER_VERSION,
        canonical_sql=canonical,
        canonical_ast_fingerprint="",
        ctes=cte_names,
        source_relations=relations,
        output_columns=outputs,
        filter_predicate=_sql(where.this, dialect) if where else None,
        filter_columns=_column_references(where.this, dialect) if where else (),
        filter_literals=(
            tuple(_sql(item, dialect) for item in where.this.find_all(exp.Literal))
            if where
            else ()
        ),
        filter_operators=(
            tuple(
                type(item).__name__.upper()
                for item in where.this.walk()
                if isinstance(item, _OPERATORS)
            )
            if where
            else ()
        ),
        joins=_joins(tree, cte_names, dialect),
        grouping=(
            tuple(_sql(item, dialect) for item in grouping.expressions)
            if grouping
            else ()
        ),
        ordering=(
            tuple(_sql(item, dialect) for item in ordering.expressions)
            if ordering
            else ()
        ),
        windows=windows,
        unresolved_stars=unresolved_stars,
    )
    fingerprint = semantic_fingerprint(
        {
            "canonical_sql": canonical,
            "dialect": dialect.lower(),
            "parser": SQL_PARSER_NAME,
            "parser_version": SQL_PARSER_VERSION,
        }
    )
    return replace(parsed, canonical_ast_fingerprint=fingerprint)


def parsed_model_to_dict(model: ParsedModel) -> dict:
    return asdict(model)


def _normalize_effective_alias_quotes(tree: exp.Expression) -> None:
    for alias in tree.find_all(exp.Alias):
        identifier = alias.args.get("alias")
        if (
            isinstance(identifier, exp.Identifier)
            and identifier.name.replace("_", "a").isalnum()
        ):
            identifier.set("quoted", False)


def _sql(expression: exp.Expression, dialect: str) -> str:
    return expression.sql(
        dialect=dialect,
        pretty=False,
        comments=False,
        normalize=True,
    )


def _relations(
    tree: exp.Select,
    cte_names: tuple[str, ...],
    dialect: str,
) -> tuple[RelationContract, ...]:
    seen: dict[tuple[str, str], RelationContract] = {}
    for table in tree.find_all(exp.Table):
        qualified = ".".join(
            part
            for part in (table.catalog, table.db, table.name)
            if isinstance(part, str) and part
        ).lower()
        alias = (table.alias_or_name or table.name).lower()
        key = (qualified, alias)
        seen[key] = RelationContract(
            qualified_name=qualified,
            alias=alias,
            is_cte=table.name.lower() in cte_names and not table.db and not table.catalog,
        )
    return tuple(seen[key] for key in sorted(seen))


def _joins(
    tree: exp.Select,
    cte_names: tuple[str, ...],
    dialect: str,
) -> tuple[JoinContract, ...]:
    result = []
    for ordinal, join in enumerate(tree.args.get("joins") or ()):
        table = join.this
        if not isinstance(table, exp.Table):
            raise SqlParseError("Derived or dynamic joined relations are unsupported.")
        qualified = ".".join(
            part
            for part in (table.catalog, table.db, table.name)
            if isinstance(part, str) and part
        ).lower()
        relation = RelationContract(
            qualified_name=qualified,
            alias=(table.alias_or_name or table.name).lower(),
            is_cte=table.name.lower() in cte_names and not table.db and not table.catalog,
        )
        predicate = join.args.get("on")
        side = (join.side or "").upper()
        kind = (join.kind or "").upper()
        join_type = " ".join(item for item in (side, kind or "JOIN") if item)
        result.append(
            JoinContract(
                ordinal=ordinal,
                join_type=join_type,
                relation=relation,
                normalized_predicate=_sql(predicate, dialect) if predicate else None,
                predicate_columns=_column_references(predicate, dialect) if predicate else (),
            )
        )
    return tuple(result)


def _output_contract(
    expression: exp.Expression,
    *,
    ordinal: int,
    dialect: str,
) -> OutputColumnContract:
    output_name = expression.alias_or_name
    if not output_name:
        raise SqlParseError(
            "Every derived output expression must have a deterministic alias."
        )
    body = expression.this if isinstance(expression, exp.Alias) else expression
    normalized = _sql(body, dialect)
    columns = _column_references(body, dialect)
    aggregations = tuple(
        _aggregation(item, dialect)
        for item in body.find_all(exp.AggFunc)
    )
    functions = tuple(
        sorted(
            {
                item.sql_name().upper()
                for item in body.find_all(exp.Func)
                if not isinstance(item, exp.AggFunc)
            }
        )
    )
    literals = tuple(
        _sql(item, dialect) for item in body.find_all(exp.Literal)
    )
    operators = tuple(
        type(item).__name__.upper()
        for item in body.walk()
        if isinstance(item, _OPERATORS)
    )
    return OutputColumnContract(
        ordinal=ordinal,
        output_name=output_name.lower(),
        normalized_expression=normalized,
        expression_fingerprint=semantic_fingerprint(
            {"dialect": dialect.lower(), "expression": normalized}
        ),
        input_columns=columns,
        source_relations=tuple(
            sorted({item.qualifier for item in columns if item.qualifier})
        ),
        aggregations=aggregations,
        functions=functions,
        literals=literals,
        operators=operators,
        has_case=any(isinstance(item, exp.Case) for item in body.walk()),
        has_window=any(isinstance(item, exp.Window) for item in body.walk()),
        data_type_state="UNKNOWN",
        lineage_derivation="CODE_DERIVED_REFERENCE",
    )


def _aggregation(item: exp.AggFunc, dialect: str) -> AggregationContract:
    distinct = isinstance(item.this, exp.Distinct) or bool(item.args.get("distinct"))
    return AggregationContract(
        function=item.sql_name().upper(),
        distinct=distinct,
        input_references=_column_references(item, dialect),
        normalized_expression=_sql(item, dialect),
    )


def _column_references(
    expression: exp.Expression,
    dialect: str,
) -> tuple[ColumnReference, ...]:
    values = {
        (
            item.name.lower(),
            item.table.lower() if item.table else None,
            _sql(item, dialect),
        )
        for item in expression.find_all(exp.Column)
    }
    return tuple(
        ColumnReference(name=name, qualifier=qualifier, normalized=normalized)
        for name, qualifier, normalized in sorted(
            values, key=lambda value: (value[1] or "", value[0], value[2])
        )
    )
