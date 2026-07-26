import json 
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.environ["NEO4J_URI"]
USERNAME = os.environ["NEO4J_USERNAME"]
PASSWORD = os.environ["NEO4J_PASSWORD"]

if not URI or not USERNAME or not PASSWORD:
    raise ValueError("Neo4j environment variables are missing.")

SEED_DIR = Path(__file__).parent/"seed_data"

def load_json(filename):
    with open(SEED_DIR / filename, "r") as f:
        return json.load(f)

def setup_constraints(session):
    """Composite uniqueness on (id, tenant_id) - this is what makes it safe
    for two tenants to have a vendor with the same id/name without collision."""
    session.run(
        "CREATE CONSTRAINT vendor_tenant IF NOT EXISTS FOR (v:Vendor) REQUIRE (v.id, v.tenant_id) IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT invoice_tenant IF NOT EXISTS FOR (i:Invoice) REQUIRE (i.id, i.tenant_id) IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT parent_tenant IF NOT EXISTS FOR (p:ParentCompany) REQUIRE (p.id, p.tenant_id) IS UNIQUE"
    )
    print("Constraints created (or already existed).")

def load_parent_companies(session, records):
    for r in records:
        session.run(
            "MERGE (p:ParentCompany{id: $id, tenant_id: $tenant_id}) SET p.name = $name",
            id = r["id"],
            tenant_id = r["tenant_id"],
            name = r["name"],
        )
    print(f"Loaded {len(records)} parent comapnies")

def load_vendors(session, records):
    for r in records:
        session.run(
            "MERGE (v:Vendor {id: $id, tenant_id: $tenant_id}) SET v.name = $name, v.tax_id = $tax_id",
            id = r["id"], tenant_id = r["tenant_id"], name = r["name"], tax_id = r["tax_id"],
        )
        if r.get("parent_company_id"):
            session.run(
                "MATCH (v:Vendor {id:$vendor_id, tenant_id:$tenant_id}) "
                "MATCH (p: ParentCompany{id:$parent_id, tenant_id:$tenant_id}) "
                "MERGE (v)-[:SUBSIDIARY_OF]->(p)",
                vendor_id=r["id"], 
                parent_id=r["parent_company_id"],
                tenant_id = r["tenant_id"],
            )
    print(f"Loaded {len(records)} vendors (with subsidiary_of links where applicable)")

def load_invoices(session, records):
    for r in records:
        session.run(
            "MERGE (i:Invoice{id: $id, tenant_id: $tenant_id}) "
            "SET i.amount = $amount, i.currency = $currency, "
            "i.issue_date = date($issue_date), "
            "i.due_date = CASE WHEN $due_date is NULL THEN NULL ELSE date($due_date) END, "
            "i.status = $status",
            id = r["id"],
            tenant_id = r["tenant_id"],
            amount = r["amount"],
            currency = r["currency"],
            issue_date = r["issue_date"],
            due_date = r["due_date"],
            status = r["status"]
        )
        session.run(
            "MATCH (i:Invoice{id: $invoice_id, tenant_id: $tenant_id}) "
            "MATCH (v:Vendor{id: $vendor_id, tenant_id: $tenant_id}) "
            "MERGE (i)-[:ISSUED_BY]->(v)",
            invoice_id= r["id"],
            vendor_id=r["vendor_id"],
            tenant_id=r["tenant_id"],
        )
    print(f"loaded {len(records)} invoice (with issued_by links)")

def load_payments(session, records):
    for r in records:
        session.run(
            "MERGE (pay:Payment{id: $id, tenant_id: $tenant_id}) "
            "SET pay.amount = $amount, pay.paid_date = date($paid_date), pay.method = $method",
            id = r["id"],
            tenant_id = r["tenant_id"],
            amount = r["amount"],
            paid_date = r["paid_date"],
            method = r["method"],
        )
        session.run(
            "MATCH (i:Invoice{id: $invoice_id, tenant_id: $tenant_id}) "
            "MATCH (pay:Payment {id: $payment_id, tenant_id: $tenant_id}) "
            "MERGE (i)-[:PAID_VIA]->(pay)",
            invoice_id = r["invoice_id"],
            payment_id = r["id"],
            tenant_id= r["tenant_id"],
        )
    print(f"Loaded {len(records)} payments (with paid_via links)")

def main():
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

    with driver.session() as session:
        setup_constraints(session)
        load_parent_companies(session, load_json("parent_companies.json"))
        load_vendors(session, load_json("vendors.json"))
        load_invoices(session, load_json("invoices.json"))
        load_payments(session, load_json("payments.json"))

    driver.close()
    print("\n all seed data loaded successfully")


if __name__ == "__main__":
    main()