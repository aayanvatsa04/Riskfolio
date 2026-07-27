# Riskfolio guest, cloud sync, API, and persistence flows

## Flow groups

- Guest mode flows run before a Supabase session exists. Saved portfolios,
  quote caches, and analysis caches stay in Dexie / IndexedDB.
- Signed-in cloud sync flows start with Google sign-in. Saved portfolios
  synchronize with Supabase, while quote and analysis caches stay browser-local.

## Arrow semantics

- `->>` represents an action, request, redirect, or write.
- `-->>` represents a response, returned data, acknowledgement, or rendered
  feedback.
- Reads are shown as a request followed by a response. Writes are one-way until
  the receiving system acknowledges them.

## Diagram sources

- Guest mode flows:
  [startup and portfolio selection](guest-1.mmd),
  [load quotes and display holdings](guest-2.mmd),
  [load and cache analyses](guest-3.mmd), and
  [save portfolio changes](guest-4.mmd).
- Signed-in cloud sync flows:
  [Google sign-in and session creation](cloud-1.mmd),
  [initial portfolio synchronization](cloud-2.mmd), and
  [synchronize portfolio changes](cloud-3.mmd).

## Persistence summary

| Data                                 | Guest mode                | Signed-in cloud sync                |
| ------------------------------------ | ------------------------- | ----------------------------------- |
| Saved portfolios                     | Dexie / IndexedDB         | Dexie plus Supabase synchronization |
| Quote and ticker metadata cache      | Dexie / IndexedDB         | Dexie / IndexedDB                   |
| Analysis response cache              | Dexie / IndexedDB         | Dexie / IndexedDB                   |
| Authentication session               | None                      | Supabase session cookies            |
| Market-data and analysis computation | FastAPI and Yahoo Finance | FastAPI and Yahoo Finance           |
