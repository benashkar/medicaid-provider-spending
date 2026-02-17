-- ============================================================
-- Medicaid Provider Data — MySQL Import Schema
-- ============================================================
--
-- This file creates the tables and indexes needed to import
-- the provider CSV exports into MySQL/MariaDB.
--
-- Usage:
--   1. Create the database:
--      CREATE DATABASE medicaid_providers CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--      USE medicaid_providers;
--
--   2. Run this schema file:
--      mysql -u root -p medicaid_providers < mysql_schema.sql
--
--   3. Load the CSV data:
--      LOAD DATA LOCAL INFILE 'providers.csv'
--        INTO TABLE providers
--        FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
--        LINES TERMINATED BY '\n'
--        IGNORE 1 ROWS;
--
--      (Repeat for each table — see LOAD DATA commands at bottom of this file)
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- PROVIDERS (from NPPES)
-- ============================================================
DROP TABLE IF EXISTS `providers`;
CREATE TABLE `providers` (
    `npi`                        CHAR(10) NOT NULL,
    `entity_type`                TINYINT NOT NULL COMMENT '1=Individual, 2=Organization',
    `organization_name`          VARCHAR(500) DEFAULT NULL,
    `last_name`                  VARCHAR(200) DEFAULT NULL,
    `first_name`                 VARCHAR(200) DEFAULT NULL,
    `middle_name`                VARCHAR(200) DEFAULT NULL,
    `credential`                 VARCHAR(100) DEFAULT NULL,
    `is_sole_proprietor`         TINYINT(1) DEFAULT NULL,
    `is_org_subpart`             TINYINT(1) DEFAULT NULL,
    `parent_org_name`            VARCHAR(500) DEFAULT NULL,
    `parent_org_tin`             VARCHAR(20) DEFAULT NULL,
    `authorized_official_last`   VARCHAR(200) DEFAULT NULL,
    `authorized_official_first`  VARCHAR(200) DEFAULT NULL,
    `authorized_official_phone`  VARCHAR(30) DEFAULT NULL,
    `enumeration_date`           DATE DEFAULT NULL,
    `last_update_date`           DATE DEFAULT NULL,
    `deactivation_date`          DATE DEFAULT NULL,
    `reactivation_date`          DATE DEFAULT NULL,
    PRIMARY KEY (`npi`),
    INDEX `idx_providers_entity_type` (`entity_type`),
    INDEX `idx_providers_org_name` (`organization_name`(100)),
    INDEX `idx_providers_last_name` (`last_name`(50)),
    INDEX `idx_providers_parent_org` (`parent_org_name`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- ADDRESSES (from NPPES)
-- ============================================================
DROP TABLE IF EXISTS `addresses`;
CREATE TABLE `addresses` (
    `address_id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `npi`                 CHAR(10) NOT NULL,
    `address_purpose`     VARCHAR(20) NOT NULL COMMENT 'MAILING or PRACTICE',
    `street_line_1`       VARCHAR(500) DEFAULT NULL,
    `street_line_2`       VARCHAR(500) DEFAULT NULL,
    `city`                VARCHAR(200) DEFAULT NULL,
    `state_code`          CHAR(2) DEFAULT NULL,
    `zip5`                CHAR(5) DEFAULT NULL,
    `zip4`                CHAR(4) DEFAULT NULL,
    `country_code`        CHAR(2) DEFAULT 'US',
    `phone`               VARCHAR(30) DEFAULT NULL,
    `fax`                 VARCHAR(30) DEFAULT NULL,
    PRIMARY KEY (`address_id`),
    UNIQUE KEY `uq_address_npi_purpose` (`npi`, `address_purpose`),
    INDEX `idx_addresses_npi` (`npi`),
    INDEX `idx_addresses_state` (`state_code`),
    INDEX `idx_addresses_zip5` (`zip5`),
    INDEX `idx_addresses_city_state` (`city`(50), `state_code`),
    CONSTRAINT `fk_addresses_provider` FOREIGN KEY (`npi`) REFERENCES `providers` (`npi`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- PROVIDER TAXONOMIES / SPECIALTIES (from NPPES)
-- ============================================================
DROP TABLE IF EXISTS `provider_taxonomies`;
CREATE TABLE `provider_taxonomies` (
    `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `npi`             CHAR(10) NOT NULL,
    `taxonomy_code`   VARCHAR(20) NOT NULL,
    `license_number`  VARCHAR(50) DEFAULT NULL,
    `license_state`   CHAR(2) DEFAULT NULL,
    `is_primary`      TINYINT(1) DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_taxonomy_npi_code` (`npi`, `taxonomy_code`),
    INDEX `idx_taxonomies_npi` (`npi`),
    INDEX `idx_taxonomies_code` (`taxonomy_code`),
    CONSTRAINT `fk_taxonomies_provider` FOREIGN KEY (`npi`) REFERENCES `providers` (`npi`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- TAXONOMY CODE REFERENCE (from NUCC)
-- ============================================================
DROP TABLE IF EXISTS `taxonomy_codes`;
CREATE TABLE `taxonomy_codes` (
    `taxonomy_code`    VARCHAR(20) NOT NULL,
    `grouping`         VARCHAR(200) DEFAULT NULL,
    `classification`   VARCHAR(200) DEFAULT NULL,
    `specialization`   VARCHAR(200) DEFAULT NULL,
    `display_name`     VARCHAR(200) DEFAULT NULL,
    `definition`       TEXT DEFAULT NULL,
    `section`          VARCHAR(50) DEFAULT NULL COMMENT 'Individual or Non-Individual',
    PRIMARY KEY (`taxonomy_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- HCPCS CODE REFERENCE
-- ============================================================
DROP TABLE IF EXISTS `hcpcs_codes`;
CREATE TABLE `hcpcs_codes` (
    `hcpcs_code`        VARCHAR(10) NOT NULL,
    `short_description` VARCHAR(500) DEFAULT NULL,
    `long_description`  TEXT DEFAULT NULL,
    `category`          VARCHAR(100) DEFAULT NULL,
    PRIMARY KEY (`hcpcs_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;


-- ============================================================
-- LOAD DATA COMMANDS
-- ============================================================
-- Run these after creating the tables to import the CSV files.
-- Adjust file paths as needed for your environment.
--
-- NOTE: You may need to enable local file loading:
--   SET GLOBAL local_infile = 1;
--   (and connect with: mysql --local-infile=1)
--
-- Load order matters due to foreign keys:
--   1. providers (no dependencies)
--   2. taxonomy_codes, hcpcs_codes (no dependencies)
--   3. addresses, provider_taxonomies (depend on providers)
-- ============================================================

/*

-- 1. Providers (~9M rows)
LOAD DATA LOCAL INFILE 'providers.csv'
INTO TABLE providers
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(npi, entity_type, organization_name, last_name, first_name,
 middle_name, credential, @is_sole, @is_sub,
 parent_org_name, parent_org_tin,
 authorized_official_last, authorized_official_first, authorized_official_phone,
 @enum_date, @update_date, @deact_date, @react_date)
SET is_sole_proprietor = IF(@is_sole='', NULL, @is_sole),
    is_org_subpart = IF(@is_sub='', NULL, @is_sub),
    enumeration_date = IF(@enum_date='', NULL, @enum_date),
    last_update_date = IF(@update_date='', NULL, @update_date),
    deactivation_date = IF(@deact_date='', NULL, @deact_date),
    reactivation_date = IF(@react_date='', NULL, @react_date);

-- 2. Taxonomy codes reference (883 rows)
LOAD DATA LOCAL INFILE 'taxonomy_codes.csv'
INTO TABLE taxonomy_codes
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(taxonomy_code, @grouping, classification, @spec, @display, @def, @section)
SET `grouping` = IF(@grouping='', NULL, @grouping),
    specialization = IF(@spec='', NULL, @spec),
    display_name = IF(@display='', NULL, @display),
    definition = IF(@def='', NULL, @def),
    section = IF(@section='', NULL, @section);

-- 3. HCPCS codes reference (~21K rows)
LOAD DATA LOCAL INFILE 'hcpcs_codes.csv'
INTO TABLE hcpcs_codes
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(hcpcs_code, @short, @long, @cat)
SET short_description = IF(@short='', NULL, @short),
    long_description = IF(@long='', NULL, @long),
    category = IF(@cat='', NULL, @cat);

-- 4. Addresses (~18M rows)
LOAD DATA LOCAL INFILE 'addresses.csv'
INTO TABLE addresses
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(npi, address_purpose, street_line_1, street_line_2,
 city, state_code, zip5, zip4, country_code, phone, fax);

-- 5. Provider taxonomies (~11M rows)
LOAD DATA LOCAL INFILE 'provider_taxonomies.csv'
INTO TABLE provider_taxonomies
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(npi, taxonomy_code, @lic_num, @lic_state, @is_primary)
SET license_number = IF(@lic_num='', NULL, @lic_num),
    license_state = IF(@lic_state='', NULL, @lic_state),
    is_primary = IF(@is_primary='', 0, @is_primary);

*/
