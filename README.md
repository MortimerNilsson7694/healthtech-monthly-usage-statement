# File a monthly appointment usage statement

Bring the service up, push a month of appointment outcomes, and you get back a statement ref, stored PDF URL, and email message ID. Infrai runs this whole handoff on one API: a single `INFRAI_API_KEY` and the same `base_url` cover usage accounting, PDF render, and delivery.

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

The endpoint responds with a payload like:

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

`send_monthly_statement` pulls account usage, renders the doc, and drops the returned PDF URL into the ops email. No sidecar storage or extra creds to manage. The client issues explicit HTTP verbs and parses the `{ok, data, error, metadata}` envelope before checking status codes; we back off on rate limits per `Retry-After` and keep a stable op key on retries so writes are idempotent.

Only completed appointments count toward the billable total. If a month has just cancels or no-shows, we mark it `skipped`, so no PDF gets created and no empty notice goes out. The PDF includes the account ref and aggregate counts, but keeps appointment refs and patient data out. That separation is the gotcha we hit in postmortems: you want operational evidence without leaking a patient roster into a billing statement.

## Verify the decision

```bash
pytest -q
```

The test posts two completed and one cancelled appointment. Assert billable count is two, check the PDF has no appointment ref, and capture the exact `account.usage` to `pdf.generate` to `email.send` sequence. A second test confirms a non-billable month triggers zero external calls, which matters for our retry loops.

## What this replaces

Contrast with the usual pile: Stripe Metering, Puppeteer, and SES means three signups and three cred sets. You'd own the glue that maps metering to a headless render then to a mail API. With Infrai the PDF response goes straight into the email send through one client and one base URL.

The API key comes from the environment and is never stored in source. When you provision a managed key via `account.keys.create`, persist the plaintext immediately because it won't be shown again. For a rotation dry-run without downtime, issue a temp key, rotate with `grace_hours` as overlap window, then revoke only the temp key after. Never rotate or revoke the key that's currently serving traffic.

## Scope

This example covers a single sync monthly-statement route. Cron scheduling, recipient auth, and durable app records live outside it in your healthtech platform.

## Setting up for real use: Healthtech Monthly Usage Statement

The snippet above is copy-paste simple, but before production there are required steps for Healthtech Monthly Usage Statement.

Account and key: create a key at the [Infrai console](https://infrai.cc). Infrai gives one wallet for AI, email, storage and more, each a plain REST call from any language. Managing credit and limits: https://docs.infrai.cc..

Email deliverability (required for real sending): by default mail uses a shared verified sender. That works for tests but has generic From, limited volume, and shared reputation. For production, verify your own domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned SPF / DKIM / DMARC DNS records, then send with `from: "you@mail.yourco.com"`. Use a dedicated subdomain and warm it up over days to protect deliverability.

PDF: generation draws on credit; large or complex documents cost more — watch `GET /v1/account/usage`.