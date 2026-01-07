# Environment-Specific Configuration

This directory contains environment-specific configuration overrides.

## Usage

Create environment-specific config files that override the default configuration:

```yaml
# local.yaml - Local development overrides
paths:
  input_folder: "C:/Users/your-username/data/input"
  output_folder: "C:/Users/your-username/data/output"

# production.yaml - Production settings
paths:
  input_folder: "/mnt/shared/production/input"
  output_folder: "/mnt/shared/production/output"
```

## Configuration Priority

1. Default config files (e.g., `config/phase2.yaml`)
2. Environment overrides (e.g., `config/environments/local.yaml`)

## Ignored Files

The following patterns are in `.gitignore` to prevent committing local paths:

- `config/environments/local.yaml`
- `config/local*.yaml`

## Example Local Configuration

Create `local.yaml` for your personal setup:

```yaml
# config/environments/local.yaml
paths:
  input_folder: "C:/path/to/your/data"
  output_folder: "C:/path/to/your/output"
  
logging:
  level: DEBUG  # More verbose logging for development
```
