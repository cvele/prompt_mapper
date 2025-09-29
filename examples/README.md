# Examples

This directory contains example movie files and configurations for testing the Prompt-Based Movie Mapper.

## Example Movie Structure

```
examples/
├── The Matrix (1999)/
│   ├── The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv
│   └── The.Matrix.1999.1080p.BluRay.x264-GROUP.srt
├── Blade Runner 2049 (2017)/
│   ├── Blade.Runner.2049.2017.2160p.UHD.BluRay.x265-GROUP.mkv
│   └── Blade.Runner.2049.2017.2160p.UHD.BluRay.x265-GROUP.en.srt
└── Serbian Movie Example/
    └── Podzemlje.1995.DVDRip.XviD-GROUP.avi
```

## Usage Examples

### Basic Scan
```bash
prompt-mapper scan examples/
```

### Custom Prompt
```bash
prompt-mapper scan examples/ --prompt "These are classic sci-fi movies with standard naming"
```

### Dry Run
```bash
prompt-mapper scan examples/ --dry-run
```

### Batch Processing
```bash
prompt-mapper scan examples/*/ --batch
```

## Test Configuration

Use the example configuration in `config/config.example.yaml` as a starting point.
