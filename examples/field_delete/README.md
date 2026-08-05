# Field delete example

This proposal deletes `order_total`. Repository inspection found that it is
the only source-schema field in the certified snapshot with supplied
field-level downstream lineage: 27 observed edges and 48 supplied paths. It
was selected from the snapshot by identity, not by schema position. No field,
consumer, or relationship was invented.

The resulting package is a generalized example certification, not the frozen
Phase 4 certification.
