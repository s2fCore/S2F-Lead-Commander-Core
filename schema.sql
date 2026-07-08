-- ──────────────────────────────────────────────────────────────────────────────
-- S2F LEAD COMMANDER CORE: DATABASE INITIALIZATION SCHEMA
-- Copyright (c) 2026 S2F Sportswear. All rights reserved.
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sportswear_leads (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    map_url TEXT UNIQUE NOT NULL,
    external_website TEXT DEFAULT 'Pending',
    phone_number VARCHAR(50) DEFAULT 'Pending',
    scan_status VARCHAR(50) DEFAULT 'Pending',
    raw_details TEXT,
    apparel_gap TEXT DEFAULT 'Unanalyzed',
    calculated_margin NUMERIC DEFAULT 0.00,
    targeted_hook TEXT DEFAULT 'Pending',
    contact_name VARCHAR(255) DEFAULT 'Decision Maker',
    contact_title VARCHAR(255) DEFAULT 'Gym Owner / Head Coach',
    personal_email TEXT DEFAULT 'Not Found',
    instagram_url TEXT,
    facebook_url TEXT,
    linkedin_url TEXT,
    tiktok_url TEXT,
    ai_winning_score INTEGER DEFAULT 0,
    ai_qualification_notes TEXT,
    email_stage INTEGER DEFAULT 1,
    last_delivery_attempt TIMESTAMP,
    delivery_status VARCHAR(50) DEFAULT 'Not Sent',
    postal_address VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_leads_scan_status ON sportswear_leads(scan_status);
CREATE INDEX IF NOT EXISTS idx_leads_map_url ON sportswear_leads(map_url);
CREATE UNIQUE INDEX IF NOT EXISTS sportswear_leads_name_key ON sportswear_leads(name);
