"""Benchmark task definitions for core capabilities."""

from __future__ import annotations

from .framework import BenchmarkSuite, BenchmarkTask


def create_core_suite() -> BenchmarkSuite:
    """Create core benchmark suite for basic agent capabilities."""
    
    suite = BenchmarkSuite(name="core")
    
    # Task 1: Simple file creation
    suite.add_task(BenchmarkTask(
        id="core-001",
        name="create_python_file",
        description="Create a simple Python file with a function",
        prompt="Create a file called hello.py that contains a function called greet() that returns 'Hello, World!'",
        expected_files=["hello.py"],
        expected_patterns=["def greet()", "return"],
        max_steps=10,
        timeout_seconds=60,
        tags=["basic", "file_creation"],
    ))
    
    # Task 2: Multi-file project
    suite.add_task(BenchmarkTask(
        id="core-002",
        name="create_multi_file_project",
        description="Create a simple multi-file Python project",
        prompt="Create a calculator project with three files: math_ops.py with add and subtract functions, calculator.py that imports and uses math_ops, and main.py that runs the calculator",
        expected_files=["math_ops.py", "calculator.py", "main.py"],
        expected_patterns=["def add(", "def subtract(", "import math_ops"],
        max_steps=20,
        timeout_seconds=120,
        tags=["multi_file", "project_structure"],
    ))
    
    # Task 3: Read and modify existing file
    suite.add_task(BenchmarkTask(
        id="core-003",
        name="modify_existing_file",
        description="Read and modify an existing file",
        prompt="I have a file called config.py with a DEBUG = False setting. Change it to DEBUG = True and add a new setting LOG_LEVEL = 'INFO'",
        expected_files=["config.py"],
        expected_patterns=["DEBUG = True", "LOG_LEVEL = 'INFO'"],
        max_steps=15,
        timeout_seconds=90,
        tags=["file_modification", "read_write"],
    ))
    
    # Task 4: Code with tests
    suite.add_task(BenchmarkTask(
        id="core-004",
        name="create_code_with_tests",
        description="Create code and corresponding tests",
        prompt="Create a utils.py file with a function called calculate_average that takes a list of numbers and returns their average. Then create test_utils.py with unit tests for this function",
        expected_files=["utils.py", "test_utils.py"],
        expected_patterns=["def calculate_average(", "def test_", "import unittest"],
        max_steps=25,
        timeout_seconds=150,
        tags=["testing", "code_quality"],
    ))
    
    # Task 5: Documentation generation
    suite.add_task(BenchmarkTask(
        id="core-005",
        name="generate_documentation",
        description="Create code with documentation",
        prompt="Create a file called api_client.py with a class called APIClient that has methods for get, post, and delete. Include docstrings for the class and all methods explaining their purpose and parameters",
        expected_files=["api_client.py"],
        expected_patterns=["class APIClient", "def get(", "def post(", "def delete(", "\"\"\""],
        max_steps=20,
        timeout_seconds=120,
        tags=["documentation", "code_quality"],
    ))
    
    # Task 6: Error handling
    suite.add_task(BenchmarkTask(
        id="core-006",
        name="implement_error_handling",
        description="Create code with proper error handling",
        prompt="Create a file_parser.py with a function parse_json_file that reads a JSON file and returns the parsed data. Include proper error handling for FileNotFoundError, JSONDecodeError, and general exceptions",
        expected_files=["file_parser.py"],
        expected_patterns=["def parse_json_file(", "try:", "except FileNotFoundError", "except", "raise"],
        max_steps=20,
        timeout_seconds=120,
        tags=["error_handling", "robustness"],
    ))
    
    # Task 7: Refactoring task
    suite.add_task(BenchmarkTask(
        id="core-007",
        name="refactor_duplicate_code",
        description="Refactor code to remove duplication",
        prompt="I have a file called handlers.py with three functions that all have the same validation logic at the start. Refactor it to extract the validation into a separate function called validate_input",
        expected_files=["handlers.py"],
        expected_patterns=["def validate_input(", "def handle_"],
        max_steps=25,
        timeout_seconds=150,
        tags=["refactoring", "code_quality"],
    ))
    
    # Task 8: Configuration file creation
    suite.add_task(BenchmarkTask(
        id="core-008",
        name="create_config_files",
        description="Create configuration files for a project",
        prompt="Create a config.yaml file with database settings (host, port, name), logging settings (level, format), and app settings (debug, version). Also create a .env.example file with the same settings as environment variables",
        expected_files=["config.yaml", ".env.example"],
        expected_patterns=["database:", "logging:", "DEBUG=", "VERSION="],
        max_steps=15,
        timeout_seconds=90,
        tags=["configuration", "project_setup"],
    ))
    
    return suite


def create_reasoning_suite() -> BenchmarkSuite:
    """Create benchmark suite for reasoning and planning capabilities."""
    
    suite = BenchmarkSuite(name="reasoning")
    
    # Task 1: Multi-step reasoning
    suite.add_task(BenchmarkTask(
        id="reason-001",
        name="multi_step_analysis",
        description="Perform multi-step analysis and implementation",
        prompt="Analyze the current directory structure, identify if there are any Python files, and if not, create a simple project structure with src/, tests/, and a README.md. If there are Python files, create a summary document listing all Python files and their purposes",
        expected_patterns=["src/", "tests/", "README.md"],
        max_steps=30,
        timeout_seconds=180,
        tags=["analysis", "multi_step"],
    ))
    
    # Task 2: Conditional logic based on context
    suite.add_task(BenchmarkTask(
        id="reason-002",
        name="context_aware_implementation",
        description="Make implementation decisions based on context",
        prompt="Check if there's a package.json file. If yes, create a JavaScript utility file. If no, check for requirements.txt and create a Python utility file. If neither exists, create both a package.json and requirements.txt with basic configurations",
        max_steps=25,
        timeout_seconds=150,
        tags=["conditional_logic", "context_aware"],
    ))
    
    # Task 3: Dependency resolution
    suite.add_task(BenchmarkTask(
        id="reason-003",
        name="dependency_aware_creation",
        description="Create files with proper dependency management",
        prompt="Create a data processing pipeline with three modules: data_loader.py, data_processor.py, and data_exporter.py. Ensure proper imports between modules and create a main.py that orchestrates the pipeline. Also create a requirements.txt with any needed dependencies",
        expected_files=["data_loader.py", "data_processor.py", "data_exporter.py", "main.py", "requirements.txt"],
        expected_patterns=["import data_loader", "import data_processor"],
        max_steps=35,
        timeout_seconds=200,
        tags=["dependencies", "project_structure"],
    ))
    
    return suite


def create_compaction_suite() -> BenchmarkSuite:
    """Create benchmark suite for context compaction capabilities."""
    
    suite = BenchmarkSuite(name="compaction")
    
    # Task 1: Long conversation handling
    suite.add_task(BenchmarkTask(
        id="compact-001",
        name="long_conversation",
        description="Handle a long conversation with multiple iterations",
        prompt="Create a file called counter.py with a Counter class. Then add an increment method. Then add a decrement method. Then add a reset method. Then add a get_value method. Finally, add a __str__ method. Each step should build on the previous one",
        expected_files=["counter.py"],
        expected_patterns=["class Counter", "def increment", "def decrement", "def reset", "def get_value", "def __str__"],
        max_steps=40,
        timeout_seconds=240,
        tags=["long_conversation", "iteration"],
    ))
    
    # Task 2: Iterative refinement
    suite.add_task(BenchmarkTask(
        id="compact-002",
        name="iterative_refinement",
        description="Iteratively refine code through multiple passes",
        prompt="Create a simple function called process_data. Then add type hints. Then add error handling. Then add logging. Then add docstrings. Finally, add unit tests. Each step should improve the previous implementation",
        expected_files=["process_data.py"],
        expected_patterns=["def process_data", "->", "try:", "logging", "\"\"\""],
        max_steps=45,
        timeout_seconds=270,
        tags=["iterative", "refinement"],
    ))
    
    return suite


def get_all_suites() -> dict[str, BenchmarkSuite]:
    """Get all benchmark suites."""
    return {
        "core": create_core_suite(),
        "reasoning": create_reasoning_suite(),
        "compaction": create_compaction_suite(),
    }
