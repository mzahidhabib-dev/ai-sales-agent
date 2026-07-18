CREATE TABLE tenants (
    tenant_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pipeline_stage (
    stage_id VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255)
);

INSERT INTO pipeline_stage (stage_id, description) VALUES
('prospecting', 'Prospecting'),
('contacted', 'Contacted'),
('meeting_booked', 'Meeting Booked'),
('handed_off', 'Handed Off');

CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prospects (
    prospect_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    company_id INT REFERENCES companies(company_id),
    status VARCHAR(50) DEFAULT 'new',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_makers (
    decision_maker_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    prospect_id INT REFERENCES prospects(prospect_id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(255),
    email VARCHAR(255),
    linkedin_url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE opportunities (
    opportunity_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    prospect_id INT REFERENCES prospects(prospect_id),
    stage_id VARCHAR(50) REFERENCES pipeline_stage(stage_id),
    value NUMERIC(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Rule 14: unique constraint ensures update_crm() is idempotent even on double-run
    CONSTRAINT uq_opportunities_tenant_prospect UNIQUE (tenant_id, prospect_id)
);


CREATE TABLE decision_cards (
    decision_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    agent_name VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    result TEXT,
    confidence NUMERIC(3, 2),
    reason TEXT[],
    sources TEXT[],
    model VARCHAR(100),
    prompt_version VARCHAR(100),
    cost_usd NUMERIC(10, 4),
    duration_seconds NUMERIC(10, 2),
    approved BOOLEAN,
    approval_required BOOLEAN,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    replay_id VARCHAR(255),
    approval_status VARCHAR(50) DEFAULT 'NOT_REQUIRED'
);

CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE handoffs (
    handoff_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    prospect_id INT REFERENCES prospects(prospect_id),
    opportunity_id INT REFERENCES opportunities(opportunity_id),
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed one tenant row
INSERT INTO tenants (tenant_id, name) VALUES ('tenant-1', 'Initial Test Tenant');

CREATE TABLE audit_logs (
    audit_id SERIAL PRIMARY KEY,
    decision_id INT REFERENCES decision_cards(decision_id),
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    agent_name VARCHAR(100),
    prompt TEXT,
    model VARCHAR(100),
    raw_output TEXT,
    validation_result JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE memory (
    memory_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(tenant_id),
    prospect_id INT REFERENCES prospects(prospect_id),
    data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_memory_tenant_prospect UNIQUE (tenant_id, prospect_id)
);
