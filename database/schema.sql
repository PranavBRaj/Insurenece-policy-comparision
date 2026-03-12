CREATE DATABASE IF NOT EXISTS insurance_compare
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE insurance_compare;

CREATE TABLE IF NOT EXISTS policies (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    filename       VARCHAR(255)  NOT NULL,
    original_name  VARCHAR(255)  NOT NULL,
    file_path      VARCHAR(500)  NOT NULL,
    file_size      INT           NOT NULL,
    mime_type      VARCHAR(100)  DEFAULT 'application/pdf',
    extracted_text LONGTEXT,
    parsed_data    JSON,
    parse_status   ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
    parse_error    TEXT,
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comparisons (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    policy1_id        INT        NOT NULL,
    policy2_id        INT        NOT NULL,
    comparison_result JSON,
    status            ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
    error_message     TEXT,
    created_at        TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cmp_policy1 FOREIGN KEY (policy1_id) REFERENCES policies(id) ON DELETE CASCADE,
    CONSTRAINT fk_cmp_policy2 FOREIGN KEY (policy2_id) REFERENCES policies(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS upload_sessions (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    session_id          VARCHAR(100)  NOT NULL UNIQUE,
    policy1_filename    VARCHAR(255),
    policy2_filename    VARCHAR(255),
    policy1_id          INT,
    policy2_id          INT,
    comparison_id       INT,
    status              ENUM('uploading','processing','completed','failed') NOT NULL DEFAULT 'uploading',
    error_message       TEXT,
    ip_address          VARCHAR(45),
    created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sess_policy1   FOREIGN KEY (policy1_id)   REFERENCES policies(id)    ON DELETE SET NULL,
    CONSTRAINT fk_sess_policy2   FOREIGN KEY (policy2_id)   REFERENCES policies(id)    ON DELETE SET NULL,
    CONSTRAINT fk_sess_cmp       FOREIGN KEY (comparison_id) REFERENCES comparisons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_policies_status    ON policies(parse_status);
CREATE INDEX idx_policies_created   ON policies(created_at);
CREATE INDEX idx_cmp_policy1        ON comparisons(policy1_id);
CREATE INDEX idx_cmp_policy2        ON comparisons(policy2_id);
CREATE INDEX idx_cmp_status         ON comparisons(status);
CREATE INDEX idx_cmp_created        ON comparisons(created_at);
CREATE INDEX idx_sess_status        ON upload_sessions(status);
CREATE INDEX idx_sess_created       ON upload_sessions(created_at);
