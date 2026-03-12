import { render, screen, waitFor } from "@testing-library/react";

import { App } from "./App";

function mockFetchSuccess() {
  const fetchMock = vi.fn();
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/health")) {
      return {
        ok: true,
        json: async () => ({
          status: "ok",
          service: "ekstrehub-api",
          environment: "development",
          mail_ingestion_enabled: true,
          masked_imap_user: "te******om",
          db_available: true
        })
      };
    }
    if (url.includes("/api/mail-ingestion/runs")) {
      return {
        ok: true,
        json: async () => ({
          items: [
            {
              id: 42,
              status: "completed",
              scanned_messages: 5,
              processed_messages: 4,
              duplicate_messages: 1,
              saved_documents: 3,
              duplicate_documents: 1,
              skipped_attachments: 0,
              failed_messages: 0,
              csv_rows_parsed: 12,
              started_at: "2026-02-21T00:00:00Z",
              finished_at: "2026-02-21T00:00:10Z"
            }
          ],
          next_cursor: null
        })
      };
    }
    if (url.includes("/api/mail-accounts")) {
      return {
        ok: true,
        json: async () => ({
          items: [
            {
              id: 3,
              provider: "gmail",
              auth_mode: "oauth_gmail",
              account_label: "Primary Gmail",
              imap_host: "imap.gmail.com",
              imap_port: 993,
              imap_user: "us******om",
              mailbox: "INBOX",
              unseen_only: true,
              fetch_limit: 20,
              retry_count: 3,
              retry_backoff_seconds: 1.5,
              is_active: true,
              created_at: "2026-02-21T00:00:00Z"
            }
          ]
        })
      };
    }
    if (url.includes("/api/parser/changes")) {
      return {
        ok: true,
        json: async () => ({
          items: [],
          status: "pending"
        })
      };
    }
    throw new Error(`Unexpected fetch in test: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders success status after API calls", async () => {
    mockFetchSuccess();

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Sistem hazir")).toBeInTheDocument();
    });
    expect(screen.getByText("ekstrehub-api")).toBeInTheDocument();
    expect(screen.getByText("TRY (TL)")).toBeInTheDocument();
    expect(screen.getByText("Run #42")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Mail & Sync")).toBeInTheDocument();
    expect(screen.getByText("Parser Approval")).toBeInTheDocument();
    expect(screen.getByText("System Logs")).toBeInTheDocument();
  });
});
