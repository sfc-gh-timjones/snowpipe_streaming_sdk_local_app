-- =============================================================
-- Security Camera Streaming Demo — Snowflake Setup
-- Run this whole file once in a Snowsight SQL worksheet.
-- BEFORE RUNNING: replace <PASTE_PUBLIC_KEY_HERE> in step 4.
-- =============================================================

USE ROLE ACCOUNTADMIN;

-- 1. Database & schema
CREATE DATABASE IF NOT EXISTS STREAMING_DEMO;
CREATE SCHEMA IF NOT EXISTS STREAMING_DEMO.SECURITY;

-- 2. Target table
CREATE OR REPLACE TABLE STREAMING_DEMO.SECURITY.CAMERA_EVENTS (
    event_id        VARCHAR,
    camera_id       VARCHAR,
    location        VARCHAR,
    zone            VARCHAR,
    event_type      VARCHAR,
    confidence      FLOAT,
    object_count    NUMBER,
    duration_ms     NUMBER,
    ingested_at     TIMESTAMP_NTZ,
    metadata        VARIANT
);

-- 3. Role with streaming permissions
CREATE ROLE IF NOT EXISTS STREAMING_DEMO_ROLE;
GRANT USAGE ON DATABASE STREAMING_DEMO TO ROLE STREAMING_DEMO_ROLE;
GRANT USAGE ON SCHEMA STREAMING_DEMO.SECURITY TO ROLE STREAMING_DEMO_ROLE;
GRANT INSERT ON TABLE STREAMING_DEMO.SECURITY.CAMERA_EVENTS TO ROLE STREAMING_DEMO_ROLE;

-- 4. Dedicated service user with key-pair auth
--    Replace <PASTE_PUBLIC_KEY_HERE> with the output of:
--      grep -v "^-" ~/.snowflake/keys/streaming_demo.pub | tr -d '\n'
CREATE USER IF NOT EXISTS STREAMING_DEMO_USER
    TYPE = SERVICE
    DEFAULT_ROLE = STREAMING_DEMO_ROLE;
ALTER USER STREAMING_DEMO_USER SET RSA_PUBLIC_KEY = '<PASTE_PUBLIC_KEY_HERE>';
GRANT ROLE STREAMING_DEMO_ROLE TO USER STREAMING_DEMO_USER;

-- 5. Copy this value into SNOWFLAKE_ACCOUNT in your .env file
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS SNOWFLAKE_ACCOUNT;

-- =============================================================
-- After streaming, query the live table:
-- =============================================================
-- SELECT COUNT(*) FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS;
-- SELECT event_id, camera_id, event_type, confidence, ingested_at
-- FROM STREAMING_DEMO.SECURITY.CAMERA_EVENTS
-- ORDER BY ingested_at DESC LIMIT 20;

-- =============================================================
-- Cleanup (when you're done with the demo)
-- =============================================================
-- DROP USER IF EXISTS STREAMING_DEMO_USER;
-- DROP ROLE IF EXISTS STREAMING_DEMO_ROLE;
-- DROP DATABASE IF EXISTS STREAMING_DEMO;
