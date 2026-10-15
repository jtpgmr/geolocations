# Defaults; override them from the command line.
PATHS					?=	alembic src
OUTPUT_FORMAT			?=	concise
RUN						?=	uv run
UV_PYTHON				?= $(shell uv python find --show-version)
SYNC_FLAGS				?=	--all-groups
FIX_FLAG				= --fix

DEFAULT_ASTRAL_FLAGS	?=	--output-format=$(OUTPUT_FORMAT)

RUFF_CHECK_FLAGS		?=	$(DEFAULT_ASTRAL_FLAGS)
RUFF_FORMAT_FLAGS		?=	$(DEFAULT_ASTRAL_FLAGS) --check
TY_FLAGS				?=	$(DEFAULT_ASTRAL_FLAGS) --error-on-warning

.PHONY: help init install setup lint-check lint format-check format type-check type-fix check fix clean

help:
	@printf '%s\n' \
		'make init				Initialize UV python project' \
		'make install			Install dependencies' \
		'make setup				Sequentially runs `init install` make commands' \
		'make lint-check		Find linting problems with `ruff check`' \
		'make lint				Fix linting problems with `ruff check`' \
		'make format-check		Find code formatting problems with `ruff format`' \
		'make format			Fix code formatting problems with `ruff format`' \
		'make type-check		Find typing-related problems with `ty`' \
		'make type-fix			Fix typing-related problems with `ty`' \
		'make check				Sequentially runs `lint-check format-check type-check` make commands' \
		'make fix				Sequentially runs `lint format type-fix` make commands' \
		'make clean				Delete Python bytecode and tooling caches'


init: pyproject.toml
	@echo "Project is initialized at $(abspath pyproject.toml)."

pyproject.toml:
	uv init --python "$(UV_PYTHON)"

install:
	uv sync $(SYNC_FLAGS)

setup: init install

lint-check:
	$(RUN) ruff check $(RUFF_CHECK_FLAGS) $(PATHS)

lint: override RUFF_CHECK_FLAGS += $(FIX_FLAG) --show-fixes --exit-zero
lint: lint-check

format-check:
	$(RUN) ruff format $(RUFF_FORMAT_FLAGS) $(PATHS)


format: override RUFF_FORMAT_FLAGS = $(RUFF_CHECK_FLAGS)
format: format-check

type-check:
	$(RUN) ty check $(TY_FLAGS) $(PATHS)

type-fix: override TY_FLAGS += $(FIX_FLAG)
type-fix: type-check

check: lint-check format-check type-check
fix: lint format type-fix

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .ruff_cache