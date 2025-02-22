# tagunmatched

## Overview
This project provides a DSL (Domain-Specific Language) syntax checker. It validates the syntax of DSL code based on predefined single and group tags.

## Features
- Checks for unmatched tags
- Supports single and group tags
- Provides detailed error messages with line and column numbers
- Unit tests included

## Requirements
- Python 3.10+
- PyYAML

## Installation
1. Clone the repository:
```sh
git clone https://github.com/ab-ten/tagunmatched.git
```
2. Navigate to the project directory:
```sh
cd tagunmatched
```
3. Install the required dependencies:
```sh
pip install pyyaml
```

## Usage
To check the syntax of a DSL file:
```sh
python tagunmatched.py [-c <path-to-config-yaml>] <path-to-dsl-file>
```

To run unit tests:
```sh
python tagunmatched.py --test
```

## Configuration
The syntax checker uses a YAML configuration file to define the single and group tags. The default configuration file is `syntax-config.yaml`. You can specify a different configuration file using the `-c` or `--config` option.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
