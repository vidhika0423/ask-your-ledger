# Seed Dataset — Ask Your Ledger

Hand-written, known-correct data for Phase 1. Nothing here is scraped or
synthetic-random — every value is deliberate, including the edge cases.

## Files

| File | Contents |
|---|---|
| `parent_companies.json` | 1 parent company (Acme Holdings) |
| `vendors.json` | 4 vendor records across 2 tenants, including one vendor with no parent company and one cross-tenant name collision |
| `invoices.json` | 6 invoices: overdue, paid, and one with a deliberately missing due date |
| `payments.json` | 1 payment record, linked to a paid invoice |
| `contracts/acme_msa_2024.txt` | A full mock master service agreement — payment terms, penalties, renewal, termination, disputes |
| `contracts/acme_digital_addendum.txt` | A short addendum, references the same payment terms as the MSA |
| `test_questions.md` | 6 ground-truth Q&A pairs to validate your system against as you build |

## Deliberate edge cases built in (don't remove these)

1. **Beta Inc (V003)** has no parent company — tests that your multi-hop
   subsidiary queries correctly exclude it, without you having to filter it
   out manually.
2. **INV-1004** has `due_date: null` — tests that entity extraction and your
   reviewer agent handle missing data honestly instead of hallucinating a date.
3. **demo-tenant-2's "Acme Corp"** shares the same `id` and `name` as
   demo-tenant-1's Acme Corp but is a completely unrelated company — this is
   your multi-tenancy isolation test. Any query scoped to one tenant that
   accidentally returns the other's data has a real bug.
4. **The termination clause in Section 4 of the MSA** deliberately mixes
   contract-lifecycle language with a payment-penalty reference in the same
   paragraph — this is the ambiguous chunk RAPTOR's GMM clustering should
   split probability across, similar to the `c5` example from the GMM lesson.

## How this feeds into later phases

- **Phase 3** loads `parent_companies.json`, `vendors.json`, `invoices.json`,
  and `payments.json` into Neo4j using `schema.cypher`, with `tenant_id`
  enforced on every node.
- **Phase 4** chunks and builds a RAPTOR tree over the two contract text files.
- **Phase 6** uses `test_questions.md` as the actual test set for your
  reviewer agent's grounding checks — this is what turns "it seems to work"
  into a real precision/recall number.

Do not swap this data out for something "cleaner" — the rough edges are the
point.
