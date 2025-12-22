# txr_automation

## Overview

### Purpose

This project consolidates the automation of transaction reporting, migrating from VBA macros to Python.

### Problem Statement

The migration is happening for ease of:

- **Maintainability**: Many automations share common functions, and it is easier to apply changes when all code is written in the same language.
- **Scalability**: The medium-term plan is to build a simple application, a Transaction Reporting tool, which will allow the team to carry out all automated reporting tasks through one streamlined channel.

### Scope

The processes being automated are:

#### Quarterly Accuracy Testing

- **Extract Generation**: Generating SQL queries by inserting transaction references provided by the user into a preset query template.
- **Report Validation**: Testing reporting data against format and logic conditions, and generating any data corrections.
- **Result Outputs**: Creation of final testing results files to be sent to a third party for upload to the Approved Reporting Mechanism (ARM).

#### Quarterly Replay

- **Data Comparison**: Comparison of third-party upload files against quarterly accuracy testing results, with corrections made to the upload files where inconsistencies exist.

## Current Status

### Migration Progress

Currently, only the replay processes are Python-based, with all of the accuracy testing still to be migrated.

### Active Components

- **VBA Macros**: Legacy components to be deprecated.
- **Python Scripts**: Current state of the replay processes and target state of the accuracy testing processes.

## Project Structure

``` Markdown
txr_automation/
├── vba/                    # Legacy VBA macros
├── python/                 # Python automation scripts
├── documentation/          # Reference data and documentation
└── README.md
```

## Key Components

### VBA Modules (Legacy)

#### ID Validation

- **BuyerIDValidation5_6.vb**: Validates buyer identification codes against format and logic rules. Supports joint account aggregation, Swedish century logic for NIDN IDs, CONCAT generation, and template-based incident code lookups.
- **SellerIDValidation5_6.vb**: Validates seller identification codes with similar functionality to buyer validation. Includes template lookup enhancements for quarterly accuracy testing.

#### Inconsistent ID Handling

- **InconsistentBuyerIDValidation1_3.vb**: Identifies and corrects inconsistent buyer IDs across records with the same Person Code. Groups records chronologically and applies validation logic to detect invalid IDs that differ over time.
- **InconsistentSellerIDValidation1_3.vb**: Identifies and corrects inconsistent seller IDs using the same methodology as the buyer version.

#### SQL Extract Generators

- **ExtractBuyerID4_1.vb**: Generates SQL query files for extracting buyer identification data from the reporting database. Batches transaction references into groups of 900 for database optimization.
- **ExtractInconsistentBuyerID1_0.vb**: Generates SQL extracts specifically for inconsistent buyer ID testing scenarios.
- **SCR_extract_generator_v1_0.vb**: Generates SQL extracts for Securities Collateral Registry (SCR) pricing data validation.

#### Data Operations

- **DataPush1_0.vb**: Pushes validated data from current workbook to target validation workbooks, updating specific columns based on transaction reference matches.
- **IncidentLookup1_1.vb**: Performs transaction reference lookups in validation workbooks and returns specified columns based on incident codes.

#### Field-Specific Validation

- **ValidateFTBDM3_0.vb**: Validates First Time Buyer Decision Maker codes for compliance with regulatory requirements.
- **ValidateFTSDM3_0.vb**: Validates First Time Seller Decision Maker codes for compliance with regulatory requirements.
- **pricing_data_validation_v1.0.vb**: Validates pricing data by checking net amount, consideration amount, and interest amount calculations.

### Python Scripts (Current)

#### Phase 2 Processor

- **phase_2_processor_v3_1.py**: Ultra-optimized processor for Phase II replay files using transaction reference lookups. Features hash table indexing for O(1) lookup performance, character encoding handling, and batch processing capabilities.

#### Phase 3 Processors

- **phase_3_processor_v4_2.py**: Ultra-optimized Phase III processor with client record matching using first name, surname, date of birth, and ID value. Implements sophisticated fuzzy matching algorithms, date parsing with multiple format support, and comprehensive error flagging.
- **phase_3_final_lookup.py**: Validates client corrections in replay files against UnaVista transaction data. Performs final verification that proposed corrections match the source reporting data before submission.

#### Utilities

- **xlsx_csv_converter.py**: Converts Excel files to CSV format and handles multi-line cells by splitting them into separate rows.

### Reference Data

Located in the `documentation/` folder:

- **country_codes.csv**: ISO country code mappings for nationality validation.
- **id_formats.csv**: Regular expression patterns and validation rules for different ID types (NIDN, CCPT, CONCAT, etc.) across various countries.
- **incident_fields.csv**: Field definitions and incident code mappings for template-based lookups.
- **Agenda.txt**: Project planning and milestone tracking.
