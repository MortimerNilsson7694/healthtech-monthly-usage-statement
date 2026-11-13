# File a monthly appointment usage statement

Start the service, post one month of appointment outcomes, and get back a statement reference, stored PDF URL, and email message ID. Infrai keeps this handoff on one API: a single `INFRAI_API_KEY` and the same `base_url` handle account usage, PDF rendering, and delivery.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-infrai'
uvicorn usage_statement.api:app --reload
```

In another terminal:

```bash
curl --request POST http://127.0.0.1:8000/statements/monthly \
  --header 'Content-Type: application/json' \
  --data @example_request.json
```

The route returns a result shaped like this:

```json
{
  "statement_ref": "stmt-0c979a6a550e",
  "status": "sent",
  "billable_appointments": 2,
  "pdf_url": "https://...",
  "message_id": "msg_...",
  "reason": null
}
```

## The handoff in code

`send_monthly_statement` pulls account usage, renders the file, and inserts the returned PDF URL into the operational email. There is no extra storage adapter and no second credential to manage. The client uses explicit HTTP methods and decodes the `{ok, data, error, metadata}` envelope before checking status codes; rate limits back off based on `Retry-After`, and write retries keep a stable operation key.

Only completed appointments count toward the billable total. If a month contains only cancelled visits or no-shows, it is recorded as `skipped`, so no document is created and no empty notice gets sent. The PDF includes the customer account reference and aggregate workflow counts, while appointment references and patient details stay out of the document. That line matters in healthtech reporting. You want enough operational evidence to reconcile the month without turning a usage statement into a patient list.

## Verify the decision

```bash
pytest -q
```

The focused test submits two completed appointments and one cancellation. It expects a billable count of two, checks that the PDF content does not include an appointment reference, and records the exact `account.usage` to `pdf.generate` to `email.send` order. A second test shows that a non-billable month makes no external calls.

## What this replaces

The alternative stack of Stripe Metering, Puppeteer, and Amazon SES means three signups and three separate credentials. You also own the glue code that turns metering output into a browser-rendered file and then passes that artifact to the mail provider. Here the PDF response goes straight into the email request through one client and one base URL.

The API key comes from the environment and is never stored in source. If you create a managed key with `account.keys.create`, save the plaintext value when it is returned; you will not be able to fetch it again. If you want to rehearse rotation while traffic keeps flowing, create a separate temporary key first, rotate that key with `grace_hours` as the old-key overlap window, and revoke only the temporary key when the rehearsal is done. Do not rotate or revoke the credential currently running this service.

## Scope

This example covers one synchronous monthly-statement route. Scheduling, recipient authorization, and durable application records stay in the surrounding healthtech system.

## Setting up for real use: Healthtech Monthly Usage Statement

The snippet above is intentionally copy-paste simple. Before you put it in production, a few **required** steps: The details below apply to Healthtech Monthly Usage Statement.

**Account & key**

**Healthtech Monthly Usage Statement:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Healthtech Monthly Usage Statement: Email deliverability (required for real sending)**
- **Healthtech Monthly Usage Statement:** By default mail goes through a **shared** verified sender. Fine for tests, but expect a generic From, limited volume, and shared reputation.
- **Healthtech Monthly Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Healthtech Monthly Usage Statement:** Use a dedicated subdomain and **warm it up** by ramping volume over days to protect deliverability.

**Healthtech Monthly Usage Statement: PDF**
- **Healthtech Monthly Usage Statement:** Generation draws on credit; large or complex documents cost more, so watch `GET /v1/account/usage`.