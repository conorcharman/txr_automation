# Transaction Reporting Automation: Unified CLI Tool

**Version:** 1.0  
**Date:** 23 December 2025  
**Status:** Planning (Begins after Phase 7 completion)  
**Dependencies:** Phases 0-7 must be complete

---

## Executive Summary

This document outlines the plan to create a unified command-line interface (CLI) tool that consolidates all transaction reporting automations into a single, user-friendly entry point. This tool will simplify workflow execution by providing guided selection of operations (extract generation, accuracy testing, or replay) and appropriate incident codes or phases.

**This is Phase 8** - to be started after successful completion of Phases 0-7 (Python refactoring and VBA migration).

### Key Benefits

- **Single Entry Point**: One command to access all automations
- **Guided Workflow**: Interactive prompts reduce user errors
- **Incident-Based Organization**: Natural grouping by business process
- **Consistent Interface**: Uniform experience across all operations
- **Foundation for GUI**: Architecture designed to support future GUI development
- **Reduced Training Time**: Simpler mental model for users

---

## Relationship to Other Phases

### Prerequisites (Must Be Complete)

✅ **Phase 0**: Existing Python replay scripts refactored  
✅ **Phase 1-7**: All VBA macros migrated to Python  
✅ **Core Libraries**: `txr_replay_core` and `txr_core` fully implemented  
✅ **All Scripts**: Individual automation scripts tested and deployed

### Connection to Medium-Term Goal

This CLI tool is designed to evolve into a **Graphical User Interface (GUI)** in the medium term:

- **Short-Term (Phase 8)**: Command-line interface with text-based menus
- **Medium-Term (Phase 9+)**: Desktop GUI application (Electron, PyQt, or similar)

**Architectural Principle**: Keep business logic separate from presentation layer to enable easy GUI transition.

---

## User Workflows

### Workflow 1: Main Menu Selection

```
$ txr-automation

╔════════════════════════════════════════════════════════════════╗
║     Transaction Reporting Automation Tool v1.0                 ║
╚════════════════════════════════════════════════════════════════╝

What would you like to do?

  [1] Extract Generation
  [2] Accuracy Testing
  [3] Replay Processing
  [4] View Recent Logs
  [5] Configuration
  [Q] Quit

Select an option:
```

### Workflow 2A: Accuracy Testing Path

```
Select an option: 2

╔════════════════════════════════════════════════════════════════╗
║     Accuracy Testing                                           ║
╚════════════════════════════════════════════════════════════════╝

Select an incident to test:

  [1]  7_37  - Inconsistent Buyer Identification Codes
  [2]  7_38  - Inconsistent Seller Identification Codes
  [3]  7_39  - Buyer ID Validation
  [4]  7_40  - Seller ID Validation
  [5]  7_41  - Buyer Decision Maker Validation
  [6]  7_42  - Seller Decision Maker Validation
  [7]  7_43  - Pricing Data Validation
  [8]  7_44  - Data Completeness Check
  [9]  Other - Enter custom incident code
  [B]  Back to main menu

Select incident:
```

After selecting an incident:

```
Select incident: 1

Incident: 7_37 - Inconsistent Buyer Identification Codes
Script: inconsistent_buyer_id_validation.py

Input file location:
  [1] Use default path: /data/accuracy_testing/7_37/input/
  [2] Specify custom path

Select option: 1

✓ Found input files:
  - buyer_data_Q4_2024.csv (1,234 records)
  - tracker.csv (567 records)

Output directory: /data/accuracy_testing/7_37/output/20241223_143022/

Proceed with accuracy testing? [Y/n]:
```

### Workflow 2B: Replay Processing Path

```
Select an option: 3

╔════════════════════════════════════════════════════════════════╗
║     Replay Processing                                          ║
╚════════════════════════════════════════════════════════════════╝

Select replay phase:

  [1] Phase 2 - Initial Processing
  [2] Phase 3 - Validation & Matching
  [3] Phase 3 Final - Incident Lookup
  [4] Full Pipeline (Phase 2 → 3 → 3 Final)
  [B] Back to main menu

Select phase:
```

After selecting a phase:

```
Select phase: 2

Phase: Phase 2 - Initial Processing
Quarter: Q4 2024

Template file:
  [1] Use default: /config/templates/phase2_template.yaml
  [2] Specify custom template

Select option: 1

✓ Template loaded: phase2_template.yaml

Input file: /data/replay/Q4_2024/phase2_input.csv
Output directory: /data/replay/Q4_2024/output/phase2/20241223_143022/

Proceed with Phase 2 processing? [Y/n]:
```

### Workflow 3: Extract Generation Path

```
Select an option: 1

╔════════════════════════════════════════════════════════════════╗
║     Extract Generation                                         ║
╚════════════════════════════════════════════════════════════════╝

Select extract type:

  [1] Buyer ID Extract
  [2] Seller ID Extract
  [3] Inconsistent Buyer ID Extract
  [4] SQL Extract (SCR)
  [B] Back to main menu

Select type:
```

---

## Architecture Design

### Layered Architecture (GUI-Ready)

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │   CLI Interface      │      │   Future GUI         │    │
│  │   (Phase 8)          │      │   (Phase 9+)         │    │
│  └──────────────────────┘      └──────────────────────┘    │
│           │                              │                   │
│           └──────────────┬───────────────┘                   │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                   Business Logic Layer                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Workflow Orchestrator                        │   │
│  │  - Extract workflows                                 │   │
│  │  - Accuracy testing workflows                        │   │
│  │  - Replay workflows                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                  │                  │            │
│  ┌────────┴────────┐  ┌──────┴──────┐  ┌───────┴─────────┐ │
│  │ Incident        │  │ Phase       │  │ Extract         │ │
│  │ Manager         │  │ Manager     │  │ Manager         │ │
│  └─────────────────┘  └─────────────┘  └─────────────────┘ │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                    Core Libraries Layer                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │ txr_replay_core  │  │ txr_core         │  │ Individual │ │
│  │ (Replay logic)   │  │ (VBA logic)      │  │ Scripts    │ │
│  └──────────────────┘  └──────────────────┘  └────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Project Structure

```
txr_automation/
├── txr_cli/                              # New CLI tool package
│   ├── __init__.py
│   ├── main.py                          # Main entry point
│   ├── menu.py                          # Menu system
│   ├── prompts.py                       # User input handling
│   │
│   ├── workflows/                       # Business logic (GUI-ready)
│   │   ├── __init__.py
│   │   ├── base.py                     # Base workflow class
│   │   ├── accuracy_testing.py         # Accuracy testing workflows
│   │   ├── replay.py                   # Replay workflows
│   │   └── extracts.py                 # Extract generation workflows
│   │
│   ├── managers/                        # Incident/Phase management
│   │   ├── __init__.py
│   │   ├── incident_manager.py         # Incident catalog & metadata
│   │   ├── phase_manager.py            # Replay phase management
│   │   └── extract_manager.py          # Extract type management
│   │
│   ├── ui/                              # Presentation logic (replaceable)
│   │   ├── __init__.py
│   │   ├── cli_renderer.py             # CLI-specific rendering
│   │   ├── progress.py                 # Progress bars/spinners
│   │   └── formatting.py               # Text formatting utilities
│   │
│   └── config/                          # CLI configuration
│       ├── __init__.py
│       ├── paths.py                    # Default paths
│       └── incidents.yaml              # Incident catalog
│
├── config/
│   ├── cli_settings.yaml               # CLI-specific settings
│   └── incident_catalog.yaml           # Master incident list
│
├── documentation/
│   └── reference_data/
│       └── incident_fields.csv         # Already exists ✅
│
└── setup.py                            # Updated to include CLI entry point
```

---

## Incident Catalog System

### Incident Metadata Structure

The tool uses [incident_fields.csv](../reference_data/incident_fields.csv) as the master catalog:

```csv
incident_code,incident_name,category,script_name,input_schema,description
7_37,Inconsistent Buyer Identification Codes,Accuracy Testing,inconsistent_buyer_id_validation.py,buyer_id_validation_input,Validates consistency of buyer ID codes across transactions
7_38,Inconsistent Seller Identification Codes,Accuracy Testing,inconsistent_seller_id_validation.py,seller_id_validation_input,Validates consistency of seller ID codes across transactions
7_39,Buyer ID Validation,Accuracy Testing,buyer_id_validation.py,buyer_id_validation_input,Validates buyer identification codes against reference data
7_40,Seller ID Validation,Accuracy Testing,seller_id_validation.py,seller_id_validation_input,Validates seller identification codes against reference data
7_41,Buyer Decision Maker Validation,Accuracy Testing,validate_ftbdm.py,ftbdm_input,Validates buyer decision maker information
7_42,Seller Decision Maker Validation,Accuracy Testing,validate_ftsdm.py,ftsdm_input,Validates seller decision maker information
7_43,Pricing Data Validation,Accuracy Testing,pricing_validation.py,pricing_input,Validates pricing and financial calculations
```

### Incident Manager Implementation

```python
# txr_cli/managers/incident_manager.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path

@dataclass
class Incident:
    """Metadata for an accuracy testing incident"""
    code: str
    name: str
    category: str
    script_name: str
    input_schema: str
    description: str
    
    @property
    def display_name(self) -> str:
        """Format for menu display"""
        return f"{self.code} - {self.name}"
    
    @property
    def default_input_path(self) -> Path:
        """Default path for incident input files"""
        return Path(f"/data/accuracy_testing/{self.code}/input/")
    
    @property
    def default_output_path(self) -> Path:
        """Default path for incident outputs"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return Path(f"/data/accuracy_testing/{self.code}/output/{timestamp}/")


class IncidentManager:
    """Manages incident catalog and metadata"""
    
    def __init__(self, catalog_path: str = "documentation/reference_data/incident_fields.csv"):
        self.catalog_path = Path(catalog_path)
        self.incidents: Dict[str, Incident] = {}
        self._load_catalog()
    
    def _load_catalog(self):
        """Load incident catalog from CSV"""
        df = pd.read_csv(self.catalog_path, encoding='utf-8')
        
        for _, row in df.iterrows():
            if row['category'] == 'Accuracy Testing':
                incident = Incident(
                    code=row['incident_code'],
                    name=row['incident_name'],
                    category=row['category'],
                    script_name=row['script_name'],
                    input_schema=row['input_schema'],
                    description=row['description']
                )
                self.incidents[incident.code] = incident
    
    def get_incident(self, code: str) -> Optional[Incident]:
        """Get incident by code"""
        return self.incidents.get(code)
    
    def list_incidents(self) -> List[Incident]:
        """Get all incidents sorted by code"""
        return sorted(self.incidents.values(), key=lambda x: x.code)
    
    def search_incidents(self, query: str) -> List[Incident]:
        """Search incidents by name or description"""
        query_lower = query.lower()
        return [
            inc for inc in self.incidents.values()
            if query_lower in inc.name.lower() 
            or query_lower in inc.description.lower()
        ]
```

---

## Phase Manager System

### Replay Phase Metadata

```python
# txr_cli/managers/phase_manager.py

from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path

@dataclass
class ReplayPhase:
    """Metadata for a replay processing phase"""
    phase_id: str
    name: str
    description: str
    script_name: str
    template_name: str
    dependencies: List[str]
    
    @property
    def display_name(self) -> str:
        return f"{self.phase_id} - {self.name}"
    
    @property
    def template_path(self) -> Path:
        return Path(f"config/templates/{self.template_name}")
    
    def get_default_paths(self, quarter: str) -> Dict[str, Path]:
        """Get default input/output paths for a quarter"""
        base = Path(f"data/replay/{quarter}")
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return {
            'input': base / f"{self.phase_id.lower().replace(' ', '_')}_input.csv",
            'output': base / f"output/{self.phase_id.lower().replace(' ', '_')}/{timestamp}/"
        }


class PhaseManager:
    """Manages replay phase metadata and workflows"""
    
    def __init__(self):
        self.phases: Dict[str, ReplayPhase] = self._initialize_phases()
    
    def _initialize_phases(self) -> Dict[str, ReplayPhase]:
        """Initialize phase metadata"""
        return {
            'phase2': ReplayPhase(
                phase_id='Phase 2',
                name='Initial Processing',
                description='Initial data processing and transformation',
                script_name='phase_2_processor.py',
                template_name='phase2_template.yaml',
                dependencies=[]
            ),
            'phase3': ReplayPhase(
                phase_id='Phase 3',
                name='Validation & Matching',
                description='Client matching and validation',
                script_name='phase_3_processor.py',
                template_name='phase3_template.yaml',
                dependencies=['phase2']
            ),
            'phase3_final': ReplayPhase(
                phase_id='Phase 3 Final',
                name='Incident Lookup',
                description='Final incident lookup and reconciliation',
                script_name='phase_3_final_lookup.py',
                template_name='phase3_final_template.yaml',
                dependencies=['phase3']
            )
        }
    
    def get_phase(self, phase_id: str) -> Optional[ReplayPhase]:
        """Get phase by ID"""
        return self.phases.get(phase_id)
    
    def list_phases(self) -> List[ReplayPhase]:
        """Get all phases in order"""
        return [
            self.phases['phase2'],
            self.phases['phase3'],
            self.phases['phase3_final']
        ]
    
    def validate_dependencies(self, phase_id: str, quarter: str) -> List[str]:
        """Check if phase dependencies are satisfied"""
        phase = self.phases[phase_id]
        missing = []
        
        for dep in phase.dependencies:
            dep_phase = self.phases[dep]
            paths = dep_phase.get_default_paths(quarter)
            if not paths['output'].exists():
                missing.append(dep)
        
        return missing
```

---

## Workflow Orchestrator

### Base Workflow Class

```python
# txr_cli/workflows/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pathlib import Path
import logging

@dataclass
class WorkflowContext:
    """Context passed between workflow steps"""
    input_paths: Dict[str, Path]
    output_path: Path
    config: Dict[str, Any]
    metadata: Dict[str, Any]


class BaseWorkflow(ABC):
    """
    Base class for all workflows.
    
    This design allows the same workflow logic to be used
    by both CLI and future GUI implementations.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def validate_inputs(self, context: WorkflowContext) -> bool:
        """Validate input files and configuration"""
        pass
    
    @abstractmethod
    def prepare(self, context: WorkflowContext) -> WorkflowContext:
        """Prepare for execution (load config, create dirs, etc.)"""
        pass
    
    @abstractmethod
    def execute(self, context: WorkflowContext) -> Dict[str, Any]:
        """Execute the main workflow logic"""
        pass
    
    @abstractmethod
    def post_process(self, context: WorkflowContext, results: Dict[str, Any]) -> None:
        """Post-processing (save logs, generate reports, etc.)"""
        pass
    
    def run(self, context: WorkflowContext) -> Dict[str, Any]:
        """Run the complete workflow"""
        self.logger.info(f"Starting workflow: {self.__class__.__name__}")
        
        # Validate
        if not self.validate_inputs(context):
            raise ValueError("Input validation failed")
        
        # Prepare
        context = self.prepare(context)
        
        # Execute
        results = self.execute(context)
        
        # Post-process
        self.post_process(context, results)
        
        self.logger.info(f"Workflow completed: {self.__class__.__name__}")
        return results
```

### Accuracy Testing Workflow

```python
# txr_cli/workflows/accuracy_testing.py

from .base import BaseWorkflow, WorkflowContext
from ..managers.incident_manager import Incident
import subprocess
from pathlib import Path

class AccuracyTestingWorkflow(BaseWorkflow):
    """Workflow for running accuracy testing on an incident"""
    
    def __init__(self, incident: Incident, **kwargs):
        super().__init__(**kwargs)
        self.incident = incident
    
    def validate_inputs(self, context: WorkflowContext) -> bool:
        """Check that required input files exist"""
        for name, path in context.input_paths.items():
            if not path.exists():
                self.logger.error(f"Input file not found: {path}")
                return False
        return True
    
    def prepare(self, context: WorkflowContext) -> WorkflowContext:
        """Create output directory"""
        context.output_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Output directory: {context.output_path}")
        return context
    
    def execute(self, context: WorkflowContext) -> Dict[str, Any]:
        """Run the incident validation script"""
        script_path = Path("scripts") / self.incident.script_name
        
        cmd = [
            "python", str(script_path),
            "--input", str(context.input_paths['main']),
            "--output", str(context.output_path),
            "--incident-code", self.incident.code
        ]
        
        if 'tracker' in context.input_paths:
            cmd.extend(["--tracker", str(context.input_paths['tracker'])])
        
        self.logger.info(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self.logger.error(f"Script failed: {result.stderr}")
            raise RuntimeError(f"Accuracy testing failed for {self.incident.code}")
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'incident_code': self.incident.code
        }
    
    def post_process(self, context: WorkflowContext, results: Dict[str, Any]) -> None:
        """Save execution log"""
        log_file = context.output_path / "execution.log"
        with open(log_file, 'w') as f:
            f.write(f"Incident: {self.incident.code}\n")
            f.write(f"Script: {self.incident.script_name}\n")
            f.write(f"\n--- STDOUT ---\n{results['stdout']}\n")
            f.write(f"\n--- STDERR ---\n{results['stderr']}\n")
        
        self.logger.info(f"Execution log saved: {log_file}")
```

---

## CLI User Interface

### Main Menu System

```python
# txr_cli/menu.py

from typing import Callable, Dict, Optional
from .ui.cli_renderer import CLIRenderer

class MenuItem:
    """Represents a menu item"""
    def __init__(self, key: str, label: str, action: Callable):
        self.key = key
        self.label = label
        self.action = action


class Menu:
    """Interactive menu system"""
    
    def __init__(self, title: str, renderer: Optional[CLIRenderer] = None):
        self.title = title
        self.items: Dict[str, MenuItem] = {}
        self.renderer = renderer or CLIRenderer()
    
    def add_item(self, key: str, label: str, action: Callable) -> None:
        """Add a menu item"""
        self.items[key] = MenuItem(key, label, action)
    
    def display(self) -> None:
        """Display the menu"""
        self.renderer.clear_screen()
        self.renderer.print_header(self.title)
        
        for key, item in self.items.items():
            self.renderer.print_menu_item(key, item.label)
        
        print()
    
    def get_selection(self) -> Optional[str]:
        """Get user selection"""
        while True:
            self.display()
            choice = input("Select an option: ").strip().upper()
            
            if choice in self.items:
                return choice
            elif choice == 'Q':
                return None
            else:
                self.renderer.print_error("Invalid selection. Please try again.")
                input("Press Enter to continue...")
```

### CLI Renderer

```python
# txr_cli/ui/cli_renderer.py

import os
from typing import List

class CLIRenderer:
    """Handles CLI rendering and formatting"""
    
    @staticmethod
    def clear_screen():
        """Clear the terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    @staticmethod
    def print_header(title: str, width: int = 64):
        """Print a formatted header"""
        print()
        print("╔" + "═" * (width - 2) + "╗")
        print("║" + title.center(width - 2) + "║")
        print("╚" + "═" * (width - 2) + "╝")
        print()
    
    @staticmethod
    def print_menu_item(key: str, label: str):
        """Print a menu item"""
        print(f"  [{key}] {label}")
    
    @staticmethod
    def print_success(message: str):
        """Print success message (green check mark)"""
        print(f"✓ {message}")
    
    @staticmethod
    def print_error(message: str):
        """Print error message (red X)"""
        print(f"✗ {message}")
    
    @staticmethod
    def print_info(message: str):
        """Print info message"""
        print(f"ℹ {message}")
    
    @staticmethod
    def print_list(items: List[str], indent: int = 2):
        """Print a list of items"""
        for item in items:
            print(" " * indent + f"- {item}")
```

---

## Main Entry Point

```python
# txr_cli/main.py

import sys
import logging
from pathlib import Path
from .menu import Menu
from .managers.incident_manager import IncidentManager
from .managers.phase_manager import PhaseManager
from .workflows.accuracy_testing import AccuracyTestingWorkflow
from .workflows.replay import ReplayWorkflow
from .ui.cli_renderer import CLIRenderer

class TXRAutomationCLI:
    """Main CLI application"""
    
    def __init__(self):
        self.renderer = CLIRenderer()
        self.incident_manager = IncidentManager()
        self.phase_manager = PhaseManager()
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('txr_cli.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('TXRAutomationCLI')
    
    def run(self):
        """Main entry point"""
        while True:
            main_menu = Menu("Transaction Reporting Automation Tool v1.0", self.renderer)
            main_menu.add_item('1', 'Extract Generation', self.extract_generation_menu)
            main_menu.add_item('2', 'Accuracy Testing', self.accuracy_testing_menu)
            main_menu.add_item('3', 'Replay Processing', self.replay_menu)
            main_menu.add_item('4', 'View Recent Logs', self.view_logs)
            main_menu.add_item('5', 'Configuration', self.configuration_menu)
            main_menu.add_item('Q', 'Quit', None)
            
            choice = main_menu.get_selection()
            
            if choice is None or choice == 'Q':
                self.renderer.print_info("Goodbye!")
                sys.exit(0)
            
            main_menu.items[choice].action()
    
    def accuracy_testing_menu(self):
        """Accuracy testing submenu"""
        incidents = self.incident_manager.list_incidents()
        
        menu = Menu("Accuracy Testing", self.renderer)
        for i, incident in enumerate(incidents, 1):
            menu.add_item(str(i), incident.display_name, 
                         lambda inc=incident: self.run_accuracy_testing(inc))
        menu.add_item('B', 'Back to main menu', None)
        
        choice = menu.get_selection()
        if choice and choice != 'B':
            menu.items[choice].action()
    
    def run_accuracy_testing(self, incident):
        """Run accuracy testing for an incident"""
        self.renderer.clear_screen()
        self.renderer.print_header(f"Accuracy Testing: {incident.display_name}")
        
        # Get input path
        print(f"\nInput file location:")
        print(f"  [1] Use default path: {incident.default_input_path}")
        print(f"  [2] Specify custom path")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            input_path = incident.default_input_path / "input.csv"
        else:
            input_path = Path(input("Enter input file path: ").strip())
        
        # Create workflow context
        from .workflows.base import WorkflowContext
        context = WorkflowContext(
            input_paths={'main': input_path},
            output_path=incident.default_output_path,
            config={},
            metadata={'incident': incident}
        )
        
        # Run workflow
        workflow = AccuracyTestingWorkflow(incident, logger=self.logger)
        
        try:
            self.renderer.print_info("Starting accuracy testing...")
            results = workflow.run(context)
            self.renderer.print_success("Accuracy testing completed!")
            self.renderer.print_info(f"Results saved to: {context.output_path}")
        except Exception as e:
            self.renderer.print_error(f"Error: {str(e)}")
        
        input("\nPress Enter to continue...")
    
    # Additional menu methods...
    def replay_menu(self):
        """Replay processing submenu"""
        # Implementation similar to accuracy_testing_menu
        pass
    
    def extract_generation_menu(self):
        """Extract generation submenu"""
        # Implementation for extract workflows
        pass
    
    def view_logs(self):
        """View recent execution logs"""
        # Implementation for log viewing
        pass
    
    def configuration_menu(self):
        """Configuration submenu"""
        # Implementation for configuration
        pass


def main():
    """Entry point for CLI tool"""
    app = TXRAutomationCLI()
    app.run()


if __name__ == '__main__':
    main()
```

---

## Implementation Plan

### Timeline: 3-4 Weeks

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 1** | Core Infrastructure | - Project structure<br>- Incident/Phase managers<br>- Base workflow class<br>- CLI renderer |
| **Week 2** | Workflows | - Accuracy testing workflow<br>- Replay workflow<br>- Extract workflow<br>- Integration with existing scripts |
| **Week 3** | CLI Interface | - Main menu system<br>- Submenus<br>- User prompts<br>- Error handling |
| **Week 4** | Testing & Polish | - Integration testing<br>- User acceptance testing<br>- Documentation<br>- Bug fixes |

### Dependencies

**Must Be Complete Before Starting:**
- ✅ All Phase 0-7 scripts functional
- ✅ `txr_replay_core` package stable
- ✅ `txr_core` package stable
- ✅ All individual scripts have CLI interfaces
- ✅ Configuration system working

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| **Script integration issues** | - Test with each script individually<br>- Use subprocess with proper error handling<br>- Validate script outputs |
| **Path management complexity** | - Centralize path configuration<br>- Use pathlib consistently<br>- Test on actual file structure |
| **User confusion** | - Clear menu labels<br>- Helpful error messages<br>- Comprehensive user testing |
| **Incident catalog maintenance** | - Keep incident_fields.csv as single source of truth<br>- Document update process<br>- Validate on load |

---

## Testing Strategy

### Unit Tests

```python
# tests/test_cli/test_incident_manager.py

def test_load_incident_catalog():
    """Test loading incident catalog from CSV"""
    manager = IncidentManager()
    assert len(manager.incidents) > 0
    assert '7_37' in manager.incidents

def test_get_incident():
    """Test retrieving incident by code"""
    manager = IncidentManager()
    incident = manager.get_incident('7_37')
    assert incident is not None
    assert incident.name == 'Inconsistent Buyer Identification Codes'

def test_incident_default_paths():
    """Test incident default path generation"""
    manager = IncidentManager()
    incident = manager.get_incident('7_37')
    assert incident.default_input_path.name == 'input'
    assert '7_37' in str(incident.default_input_path)
```

### Integration Tests

```python
# tests/test_cli/test_workflows.py

def test_accuracy_testing_workflow(tmp_path):
    """Test accuracy testing workflow end-to-end"""
    # Create test input file
    input_file = tmp_path / "input.csv"
    input_file.write_text("Transaction_Reference,Account_ID\nT001,A001")
    
    # Create context
    context = WorkflowContext(
        input_paths={'main': input_file},
        output_path=tmp_path / "output",
        config={},
        metadata={}
    )
    
    # Mock incident
    incident = Incident(
        code='7_37',
        name='Test Incident',
        category='Accuracy Testing',
        script_name='test_script.py',
        input_schema='test_schema',
        description='Test'
    )
    
    # Run workflow
    workflow = AccuracyTestingWorkflow(incident)
    # Test would need actual script or mock subprocess
```

### User Acceptance Testing

**Test Scenarios:**

1. **Happy Path: Run Accuracy Testing**
   - User selects accuracy testing
   - Chooses incident 7_37
   - Uses default paths
   - Verifies output files created

2. **Happy Path: Run Replay Pipeline**
   - User selects replay processing
   - Chooses Phase 2
   - Specifies custom template
   - Verifies processing completes

3. **Error Handling: Missing Input File**
   - User selects workflow
   - Input file doesn't exist
   - Verify clear error message
   - User can retry with correct path

4. **Error Handling: Script Failure**
   - Workflow starts
   - Underlying script fails
   - Verify error logged
   - User can view error details

---

## Documentation Requirements

### User Guide

Create `documentation/user_guides/cli_tool_guide.md` with:

1. **Installation**
   - Installing the CLI tool
   - Setting up environment
   - Configuration

2. **Getting Started**
   - First-time setup
   - Running your first workflow
   - Understanding output

3. **Workflow Guides**
   - Accuracy testing workflows
   - Replay workflows
   - Extract generation workflows

4. **Incident Reference**
   - List of all incident codes
   - What each incident validates
   - Input/output specifications

5. **Troubleshooting**
   - Common errors
   - Log file locations
   - Getting help

### Developer Documentation

Create `documentation/developer/cli_architecture.md` with:

1. **Architecture Overview**
   - Layered design
   - Workflow pattern
   - GUI-ready design

2. **Adding New Workflows**
   - Extending BaseWorkflow
   - Registering with manager
   - Testing workflows

3. **Adding New Incidents**
   - Updating incident_fields.csv
   - Script requirements
   - Testing integration

4. **GUI Migration Path**
   - Separation of concerns
   - Reusable components
   - Frontend framework options

---

## Future GUI Considerations

### Design Principles for GUI Migration

1. **Separation of Concerns**
   - ✅ Business logic in `workflows/` (reusable)
   - ✅ Presentation logic in `ui/` (replaceable)
   - ✅ Data management in `managers/` (reusable)

2. **Framework Options**

   **Option A: Electron (Web-based)**
   - Pros: Cross-platform, modern UI, familiar tech stack
   - Cons: Larger bundle size, more complex deployment

   **Option B: PyQt/PySide (Native)**
   - Pros: Native performance, Python-native, smaller footprint
   - Cons: Steeper learning curve, platform-specific styling

   **Option C: Tkinter (Built-in)**
   - Pros: No dependencies, lightweight, simple
   - Cons: Less modern look, limited widgets

3. **GUI Workflow Pattern**

```python
# Future GUI implementation would use same workflows:

class GUIAccuracyTestingController:
    """GUI controller for accuracy testing"""
    
    def __init__(self, ui_view):
        self.view = ui_view
        self.workflow = AccuracyTestingWorkflow(incident)
    
    def on_run_button_clicked(self):
        """Handle run button click"""
        # Get inputs from UI
        context = self._build_context_from_ui()
        
        # Run same workflow as CLI
        results = self.workflow.run(context)
        
        # Update UI with results
        self.view.show_results(results)
```

4. **Shared Components**
   - ✅ All `managers/` classes work with GUI
   - ✅ All `workflows/` classes work with GUI
   - ✅ Only `ui/` layer needs replacement
   - ✅ Same configuration and incident catalog

---

## Success Criteria

### Functional Requirements

- ✅ **Menu Navigation**: All menus navigable and intuitive
- ✅ **Incident Selection**: All incidents selectable and launchable
- ✅ **Replay Phases**: All phases executable
- ✅ **Extract Generation**: All extract types working
- ✅ **Error Handling**: Clear error messages for all failure modes
- ✅ **Path Management**: Default and custom paths working
- ✅ **Output Organization**: Outputs organized by incident/phase/timestamp

### User Experience Requirements

- ✅ **Ease of Use**: Non-technical users can operate without documentation
- ✅ **Feedback**: Clear progress indicators and status messages
- ✅ **Error Recovery**: Users can correct mistakes and retry
- ✅ **Documentation**: Comprehensive user guide available
- ✅ **Performance**: Menus responsive, no noticeable lag

### Technical Requirements

- ✅ **Maintainability**: Code follows Python best practices
- ✅ **Testability**: All components have unit tests
- ✅ **Extensibility**: Easy to add new incidents/phases/workflows
- ✅ **GUI-Ready**: Architecture supports GUI migration
- ✅ **Logging**: All operations logged for debugging

---

## Conclusion

**Phase 8** provides a unified interface for all transaction reporting automations, significantly improving the user experience while laying the foundation for future GUI development.

**Key Benefits:**

1. **Immediate Value**: Users get simplified access to all tools
2. **Reduced Training**: Single interface to learn
3. **Better Organization**: Incident-based structure matches business processes
4. **Future-Proof**: Architecture supports GUI migration
5. **Maintainable**: Clear separation of concerns

**Timeline: 3-4 weeks** after Phase 7 completion.

**Dependencies:** Phases 0-7 must be fully complete and stable.

**Next Steps After Phase 8:**

- Gather user feedback on CLI tool
- Identify most-used workflows for GUI prioritization
- Begin planning Phase 9 (GUI development)
- Consider additional automation opportunities

---

## Appendices

### Appendix A: Entry Point Configuration

Update `setup.py` to include CLI entry point:

```python
setup(
    name='txr-automation',
    version='1.0.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'txr-automation=txr_cli.main:main',
            'txr=txr_cli.main:main',  # Short alias
        ],
    },
    # ... other setup config
)
```

### Appendix B: Configuration File

Sample `config/cli_settings.yaml`:

```yaml
cli:
  default_paths:
    accuracy_testing: /data/accuracy_testing
    replay: /data/replay
    extracts: /data/extracts
  
  logging:
    level: INFO
    file: txr_cli.log
  
  ui:
    width: 64
    clear_screen: true
    use_colors: true

incidents:
  catalog_path: documentation/reference_data/incident_fields.csv
  auto_create_output_dirs: true

replay:
  default_quarter: Q4_2024
  template_dir: config/templates
```

### Appendix C: Incident Codes Reference

Current incident codes from [incident_fields.csv](../reference_data/incident_fields.csv):

- **7_37**: Inconsistent Buyer Identification Codes
- **7_38**: Inconsistent Seller Identification Codes
- **7_39**: Buyer ID Validation
- **7_40**: Seller ID Validation
- **7_41**: Buyer Decision Maker Validation
- **7_42**: Seller Decision Maker Validation
- **7_43**: Pricing Data Validation

(More to be added as VBA scripts are migrated)

---

**Document Version History:**

- v1.0 (23 Dec 2025): Initial Phase 8 CLI tool plan

**Status:** Planning - To be implemented after Phase 7 completion
