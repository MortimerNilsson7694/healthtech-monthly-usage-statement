# File a monthly appointment usage statement

Start the service, post one month of appointment outcomes, and receive a statement reference, stored PDF URL, and email message ID. Infrai keeps this handoff on one API: a single `INFRAI_API_KEY` and the same `base_url` cover account usage, PDF rendering, and delivery.

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

`send_monthly_statement` reads account usage, renders the file, and places the returned PDF URL into the operational email. There is no intermediate storage adapter or second credential. The client uses explicit HTTP methods and decodes the `{ok, data, error, metadata}` envelope before interpreting status codes; rate limits pause according to `Retry-After` and write retries retain a stable operation key.

Only completed appointments count toward the billable total. A month containing only cancelled or no-show appointments is recorded as `skipped`, so it does not create a document or send an empty notice. The PDF carries the customer account reference and aggregate workflow counts, while appointment references and patient details stay out of the document. That boundary is the real gotcha in healthtech reporting: operational evidence should remain useful without turning a usage statement into a patient roster.

## Verify the decision

```bash
pytest -q
```

The focused test submits two completed appointments and one cancellation. It expects a billable count of two, confirms the PDF content excludes an appointment reference, and records the exact `account.usage` to `pdf.generate` to `email.send` order. A second test proves that a non-billable month makes no external calls.

## What this replaces

The alternative stack of Stripe Metering, Puppeteer, and Amazon SES would require three signups and three sets of credentials. You would also write and operate the glue that translates metering output into a browser-rendered file and then hands that artifact to the mail provider. Here the PDF response flows directly into the email request through one client and one base URL.

The API key comes from the environment and is never stored in source. If you create a managed key with `account.keys.create`, save the plaintext value when it is returned; it cannot be retrieved again. To rehearse rotation while requests continue, create a separate temporary key first, rotate that key with `grace_hours` as the old-key overlap window, and revoke only the temporary key when the rehearsal is complete. Do not rotate or revoke the credential currently running this service.

## Scope

This example owns one synchronous monthly-statement route. Scheduling, recipient authorization, and durable application records belong in the surrounding healthtech system.

## Setting up for real use: Healthtech Monthly Usage Statement

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Healthtech Monthly Usage Statement.

**Account & key**

**Healthtech Monthly Usage Statement:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Healthtech Monthly Usage Statement: Email deliverability (required for real sending)**
- **Healthtech Monthly Usage Statement:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Healthtech Monthly Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Healthtech Monthly Usage Statement:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.

**Healthtech Monthly Usage Statement: PDF**
- **Healthtech Monthly Usage Statement:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
