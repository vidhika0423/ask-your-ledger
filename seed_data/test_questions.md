# Ground-Truth Test Questions

Use these to sanity-check every phase — the graph traversal in Phase 3, RAPTOR
retrieval in Phase 4, and the reviewer agent's grounding checks in Phase 6.
Each answer is derivable *only* from the seed data files in this folder.

---

**Q1: Which invoices from subsidiaries of Acme Holdings are overdue?**
Expected answer: INV-1001 (Acme Corp, $12,500) and INV-1003 (Acme Digital, $8,700).
Reasoning: Acme Corp and Acme Digital are both subsidiaries of Acme Holdings (PC001).
INV-1005 (Beta Inc) is overdue too, but Beta Inc has no parent company, so it must
NOT appear in this specific query — this is the key traversal test from Phase 3.

**Q2: What is the late payment penalty for Acme Corp invoices?**
Expected answer: 1.5% per month on the outstanding balance, per Section 2 of
acme_msa_2024.txt. This tests RAPTOR retrieval reaching the right leaf/summary node.

**Q3: Has INV-1002 been paid, and how?**
Expected answer: Yes — paid via ACH (PAY-01) on 2026-06-05, $3,200. Tests a simple
single-hop Invoice → Payment traversal.

**Q4: What happens if Acme Digital terminates the contract right before renewal?**
Expected answer: Per Section 4 of acme_msa_2024.txt — any volume discount for the
upcoming term is forfeited, and outstanding late penalties remain payable regardless
of termination. This is the deliberately cross-topic clause (termination + payment
penalty in one sentence) meant to test RAPTOR's soft/GMM clustering — this single
chunk should reasonably show up whether the query is framed as being about
termination OR about payment penalties.

**Q5 (edge case — should be refused or flagged low-confidence): What is the due
date for INV-1004?**
Expected answer: The system should NOT invent a due date. INV-1004 has
`due_date: null` deliberately. A correct system either says "no due date on
record" or escalates rather than guessing — this is your reviewer agent's
missing-data test.

**Q6 (edge case — tenant isolation): List all invoices for Acme Corp, scoped to
demo-tenant-1.**
Expected answer: INV-1001 and INV-1002 only. INV-2001 belongs to a *different*
"Acme Corp" under demo-tenant-2 and must never appear. If it does, your tenant
scoping in Phase 3 has a bug.
