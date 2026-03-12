# Data Model Draft

## Core Tables

### `users`

- `id` (pk)
- `email`
- `timezone`
- `created_at`

### `mail_accounts`

- `id` (pk)
- `provider` (gmail/outlook/custom)
- `account_label`
- `imap_host`
- `imap_port`
- `imap_user`
- `imap_password` (MVP, sonraki fazda secret ref'e tasinacak)
- `mailbox`
- `unseen_only`
- `fetch_limit`
- `retry_count`
- `retry_backoff_seconds`
- `is_active`
- `created_at`

### `cards`

- `id` (pk)
- `user_id` (fk -> users)
- `bank_name`
- `card_alias`
- `card_last4`
- `statement_day` (opsiyonel)
- `default_due_day` (opsiyonel)
- `is_active`
- `created_at`

### `emails_ingested`

- `id` (pk)
- `mail_account_id` (fk -> mail_accounts, opsiyonel)
- `message_id` (unique)
- `sender`
- `subject`
- `received_at`
- `status` (processed/failed/ignored)
- `raw_storage_key` (opsiyonel)
- `created_at`

### `statement_documents`

- `id` (pk)
- `email_ingested_id` (fk -> emails_ingested)
- `file_name`
- `mime_type`
- `storage_key`
- `doc_hash`
- `created_at`

### `statements`

- `id` (pk)
- `user_id` (fk -> users)
- `card_id` (fk -> cards)
- `statement_document_id` (fk -> statement_documents)
- `period_start`
- `period_end`
- `total_debt`
- `minimum_payment`
- `due_date`
- `currency`
- `parse_confidence`
- `parser_version_id` (fk -> parser_versions)
- `status` (accepted/review_needed)
- `created_at`

### `statement_items`

- `id` (pk)
- `statement_id` (fk -> statements)
- `item_date`
- `description`
- `amount`
- `item_type` (spend/fee/interest/other)
- `is_fee_candidate`
- `created_at`

### `fees_detected`

- `id` (pk)
- `statement_id` (fk -> statements)
- `statement_item_id` (fk -> statement_items)
- `fee_type` (annual_fee/late_fee/other)
- `confidence`
- `requires_review`
- `created_at`

### `parser_versions`

- `id` (pk)
- `bank_name`
- `parser_key`
- `version`
- `status` (active/candidate/deprecated)
- `created_by` (system/user)
- `created_at`

### `parser_change_requests`

- `id` (pk)
- `bank_name`
- `current_parser_version_id` (fk -> parser_versions)
- `candidate_parser_version_id` (fk -> parser_versions)
- `reason` (drift_detected/manual)
- `validation_score`
- `approval_status` (pending/approved/rejected)
- `approved_by`
- `approved_at`
- `created_at`

### `reports_monthly`

- `id` (pk)
- `user_id` (fk -> users)
- `year`
- `month`
- `total_debt`
- `total_minimum_payment`
- `total_fees`
- `created_at`

### `audit_logs`

- `id` (pk)
- `actor_type` (system/user)
- `actor_id`
- `action`
- `entity_type`
- `entity_id`
- `metadata_json`
- `created_at`

## Notes

- Tum finansal tutarlar decimal tipte saklanmali.
- Tarihler timezone-aware olarak normalize edilmeli.
- `message_id` + `doc_hash` uzerinden duplicate ingestion engellenmeli.
