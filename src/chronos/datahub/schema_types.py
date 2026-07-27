"""Centralized normalization for DataHub's generic schema field types."""

from __future__ import annotations

from enum import Enum


class NormalizedFieldType(str, Enum):
    """CHRONOS representation of DataHub field type categories."""

    NUMBER = "Number"
    STRING = "String"
    BOOLEAN = "Boolean"
    DATE = "Date"
    TIME = "Time"
    BYTES = "Bytes"
    MAP = "Map"
    ARRAY = "Array"
    RECORD = "Record"
    NULL = "Null"
    UNKNOWN = "Unknown"


_DATAHUB_TYPE_NAMES = {
    "Number": NormalizedFieldType.NUMBER,
    "NumberTypeClass": NormalizedFieldType.NUMBER,
    "String": NormalizedFieldType.STRING,
    "StringTypeClass": NormalizedFieldType.STRING,
    "Boolean": NormalizedFieldType.BOOLEAN,
    "BooleanTypeClass": NormalizedFieldType.BOOLEAN,
    "Date": NormalizedFieldType.DATE,
    "DateTypeClass": NormalizedFieldType.DATE,
    "Time": NormalizedFieldType.TIME,
    "TimeTypeClass": NormalizedFieldType.TIME,
    "Bytes": NormalizedFieldType.BYTES,
    "BytesTypeClass": NormalizedFieldType.BYTES,
    "Map": NormalizedFieldType.MAP,
    "MapTypeClass": NormalizedFieldType.MAP,
    "Array": NormalizedFieldType.ARRAY,
    "ArrayTypeClass": NormalizedFieldType.ARRAY,
    "Record": NormalizedFieldType.RECORD,
    "RecordTypeClass": NormalizedFieldType.RECORD,
    "Null": NormalizedFieldType.NULL,
    "NullTypeClass": NormalizedFieldType.NULL,
}


def normalize_datahub_type(
    datahub_type_name: str | None,
) -> NormalizedFieldType:
    """Map a DataHub generic type name without guessing from native SQL text."""

    if datahub_type_name is None:
        return NormalizedFieldType.UNKNOWN
    return _DATAHUB_TYPE_NAMES.get(
        datahub_type_name,
        NormalizedFieldType.UNKNOWN,
    )
