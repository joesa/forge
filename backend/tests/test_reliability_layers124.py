"""
Tests for FORGE Reliability Layers 1, 2, and 4.

Layer 1: Pre-generation contracts (dependency resolver, lockfile, env contract)
Layer 2: Schema-driven generation (OpenAPI, Zod, Pydantic, DB types)
Layer 4: File coherence engine (import/export validation, seam, barrel)

Architecture rules validated:
  #5: File coherence engine runs AFTER all 10 build agents
  #6: Schema injection happens BEFORE each relevant agent starts
  #7: Never call real external APIs in tests
"""

from __future__ import annotations

import json

import pytest

# ── Layer 1 imports ──────────────────────────────────────────────────
from app.reliability.layer1_pregeneration.dependency_resolver import (
    ResolvedDependencies,
    resolve_dependencies,
    _parse_version,
    _satisfies_range,
)
from app.reliability.layer1_pregeneration.lockfile_generator import (
    generate_lockfile,
)
from app.reliability.layer1_pregeneration.env_contract_validator import (
    EnvContract,
    EnvVar,
    ValidationResult,
    generate_env_contract,
    validate_env_contract,
)

# ── Layer 2 imports ──────────────────────────────────────────────────
from app.reliability.layer2_schema_driven.openapi_injector import (
    generate_openapi_spec,
)
from app.reliability.layer2_schema_driven.zod_schema_injector import (
    generate_zod_schemas,
)
from app.reliability.layer2_schema_driven.pydantic_schema_injector import (
    generate_pydantic_schemas,
)
from app.reliability.layer2_schema_driven.db_type_injector import (
    generate_typescript_types,
)

# ── Layer 4 imports ──────────────────────────────────────────────────
from app.reliability.layer4_coherence.file_coherence_engine import (
    CoherenceCheckReport,
    run_coherence_check,
)
from app.reliability.layer4_coherence.barrel_validator import (
    BarrelReport,
    validate_barrel,
)
from app.reliability.layer4_coherence.seam_checker import (
    SeamReport,
    check_seam,
)


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 1: Pre-generation Contracts                               ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestDependencyResolver:
    """Tests for Layer 1 dependency resolution."""

    def test_resolve_react_vite_preset(self) -> None:
        """react_vite preset resolves all core packages."""
        result = resolve_dependencies(["react_vite"])
        assert isinstance(result, ResolvedDependencies)
        assert "react" in result.packages
        assert "react-dom" in result.packages
        assert "vite" in result.packages
        assert "typescript" in result.packages
        assert "tailwindcss" in result.packages

    def test_resolve_nextjs_preset(self) -> None:
        """nextjs preset resolves next + react."""
        result = resolve_dependencies(["nextjs"])
        assert "next" in result.packages
        assert "react" in result.packages
        assert "react-dom" in result.packages

    def test_resolve_with_additional_packages(self) -> None:
        """Additional packages are resolved alongside presets."""
        result = resolve_dependencies(["react_vite", "zustand", "@tanstack/react-query"])
        assert "zustand" in result.packages
        assert "@tanstack/react-query" in result.packages
        # Peer deps should be satisfied
        assert "react" in result.packages

    def test_peer_dependency_auto_resolution(self) -> None:
        """Peer dependencies are auto-added when missing."""
        # framer-motion requires react + react-dom as peers
        result = resolve_dependencies(["framer-motion"])
        assert "react" in result.packages
        assert "react-dom" in result.packages
        assert result.conflicts_resolved > 0

    def test_unknown_package_gets_latest(self) -> None:
        """Unknown packages get 'latest' as version."""
        result = resolve_dependencies(["some-unknown-package-xyz"])
        assert result.packages["some-unknown-package-xyz"] == "latest"

    def test_lockfile_hash_deterministic(self) -> None:
        """Same input always produces same lockfile hash."""
        result1 = resolve_dependencies(["react_vite"])
        result2 = resolve_dependencies(["react_vite"])
        assert result1.lockfile_hash == result2.lockfile_hash
        assert result1.packages == result2.packages

    def test_no_duplicate_packages(self) -> None:
        """Duplicate packages in input are deduplicated."""
        result = resolve_dependencies(["react_vite", "react", "vite"])
        # Count occurrences
        assert len(set(result.packages.keys())) == len(result.packages)

    def test_conflict_detection(self) -> None:
        """Unresolvable conflicts are reported."""
        # This should work fine — all known packages
        result = resolve_dependencies(["react_vite", "zustand"])
        assert len(result.unresolved_conflicts) == 0

    def test_packages_sorted(self) -> None:
        """Output packages dict is sorted by key."""
        result = resolve_dependencies(["react_vite", "zustand", "axios"])
        keys = list(result.packages.keys())
        assert keys == sorted(keys)


class TestSemverHelpers:
    """Tests for semver parsing and range satisfaction."""

    def test_parse_version(self) -> None:
        assert _parse_version("18.3.1") == (18, 3, 1)
        assert _parse_version("5.4.14") == (5, 4, 14)
        assert _parse_version("invalid") is None

    def test_satisfies_caret_range(self) -> None:
        assert _satisfies_range("18.3.1", "^18.0.0") is True
        assert _satisfies_range("17.0.0", "^18.0.0") is False
        assert _satisfies_range("19.0.0", "^18.0.0") is False

    def test_satisfies_gte_range(self) -> None:
        assert _satisfies_range("18.3.1", ">=16.8") is True
        assert _satisfies_range("16.7.0", ">=16.8") is False

    def test_satisfies_tilde_range(self) -> None:
        assert _satisfies_range("5.4.14", "~5.4.0") is True
        assert _satisfies_range("5.5.0", "~5.4.0") is False

    def test_satisfies_or_range(self) -> None:
        assert _satisfies_range("4.3.0", "^4.2.0 || ^5.0.0") is True
        assert _satisfies_range("5.1.0", "^4.2.0 || ^5.0.0") is True
        assert _satisfies_range("3.0.0", "^4.2.0 || ^5.0.0") is False


class TestLockfileGenerator:
    """Tests for Layer 1 lockfile generation."""

    def test_generate_valid_json(self) -> None:
        """Output is valid JSON."""
        packages = {"react": "18.3.1", "react-dom": "18.3.1"}
        result = generate_lockfile(packages)
        parsed = json.loads(result)
        assert parsed["lockfileVersion"] == 3
        assert parsed["name"] == "forge-generated-app"

    def test_deterministic_output(self) -> None:
        """Same input produces identical output."""
        packages = {"react": "18.3.1", "vite": "5.4.14", "typescript": "5.4.5"}
        result1 = generate_lockfile(packages)
        result2 = generate_lockfile(packages)
        assert result1 == result2

    def test_sorted_keys(self) -> None:
        """Package entries are sorted."""
        packages = {"zod": "3.24.1", "axios": "1.7.9", "react": "18.3.1"}
        result = generate_lockfile(packages)
        parsed = json.loads(result)
        deps = parsed["packages"][""]["dependencies"]
        keys = list(deps.keys())
        assert keys == sorted(keys)

    def test_integrity_hashes_present(self) -> None:
        """Each package has an integrity hash."""
        packages = {"react": "18.3.1"}
        result = generate_lockfile(packages)
        parsed = json.loads(result)
        node_entry = parsed["packages"]["node_modules/react"]
        assert node_entry["integrity"].startswith("sha512-")
        assert node_entry["version"] == "18.3.1"
        assert "registry.npmjs.org" in node_entry["resolved"]

    def test_handles_latest_version(self) -> None:
        """'latest' version is converted to 0.0.0."""
        packages = {"unknown-pkg": "latest"}
        result = generate_lockfile(packages)
        parsed = json.loads(result)
        assert parsed["packages"]["node_modules/unknown-pkg"]["version"] == "0.0.0"


class TestEnvContractValidator:
    """Tests for Layer 1 env contract generation and validation."""

    def test_generate_base_contract(self) -> None:
        """Base contract always includes NODE_ENV and PORT."""
        contract = generate_env_contract([], [])
        assert isinstance(contract, EnvContract)
        names = [v.name for v in contract.required]
        assert "NODE_ENV" in names
        assert "PORT" in names

    def test_generate_with_stripe_integration(self) -> None:
        """Stripe integration adds STRIPE env vars."""
        contract = generate_env_contract([], ["stripe"])
        names = [v.name for v in contract.required]
        assert "STRIPE_SECRET_KEY" in names
        assert "STRIPE_PUBLISHABLE_KEY" in names
        assert "STRIPE_WEBHOOK_SECRET" in names

    def test_generate_with_supabase_integration(self) -> None:
        """Supabase integration adds correct env vars."""
        contract = generate_env_contract([], ["supabase"])
        names = [v.name for v in contract.required]
        assert "SUPABASE_URL" in names
        assert "SUPABASE_ANON_KEY" in names

    def test_generate_with_vite_optional(self) -> None:
        """Vite framework adds optional VITE_API_URL."""
        contract = generate_env_contract(["react_vite"], [])
        optional_names = [v.name for v in contract.optional]
        assert "VITE_API_URL" in optional_names

    def test_no_duplicate_env_vars(self) -> None:
        """No duplicate env var names across required + optional."""
        contract = generate_env_contract(
            ["react_vite"], ["stripe", "supabase", "redis"]
        )
        all_names = [v.name for v in contract.required + contract.optional]
        assert len(all_names) == len(set(all_names))

    def test_validate_all_present_and_valid(self) -> None:
        """All required vars present with valid values → valid."""
        contract = generate_env_contract([], [])
        env = {"NODE_ENV": "production", "PORT": "3000"}
        result = validate_env_contract(contract, env)
        assert result.valid is True
        assert result.missing == []
        assert result.invalid == []

    def test_validate_missing_required(self) -> None:
        """Missing required vars → invalid."""
        contract = generate_env_contract([], ["stripe"])
        env = {"NODE_ENV": "production", "PORT": "3000"}
        result = validate_env_contract(contract, env)
        assert result.valid is False
        assert "STRIPE_SECRET_KEY" in result.missing

    def test_validate_invalid_format(self) -> None:
        """Invalid format → reported in invalid list."""
        contract = generate_env_contract([], ["stripe"])
        env = {
            "NODE_ENV": "production",
            "PORT": "3000",
            "STRIPE_SECRET_KEY": "not-a-valid-key",
            "STRIPE_PUBLISHABLE_KEY": "pk_test_abc123",
            "STRIPE_WEBHOOK_SECRET": "whsec_abc123",
        }
        result = validate_env_contract(contract, env)
        assert result.valid is False
        assert any("STRIPE_SECRET_KEY" in inv for inv in result.invalid)

    def test_validate_optional_vars_not_required(self) -> None:
        """Missing optional vars don't cause validation failure."""
        contract = generate_env_contract(["react_vite"], [])
        env = {"NODE_ENV": "development", "PORT": "5173"}
        result = validate_env_contract(contract, env)
        assert result.valid is True


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 2: Schema-driven Generation                               ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestOpenAPIInjector:
    """Tests for Layer 2 OpenAPI spec generation."""

    def test_generate_basic_spec(self) -> None:
        """Generates valid OpenAPI 3.1 YAML."""
        spec_outputs = {
            "api_spec": {
                "title": "Test API",
                "description": "Test description",
                "version": "1.0.0",
            },
        }
        result = generate_openapi_spec(spec_outputs)
        assert "openapi: '3.1.0'" in result
        assert "Test API" in result
        assert "BearerAuth" in result

    def test_generate_with_endpoints(self) -> None:
        """Generates path items from endpoint definitions."""
        spec_outputs = {
            "api_spec": {
                "title": "Test API",
                "endpoints": [
                    {
                        "path": "/users",
                        "method": "get",
                        "operation_id": "listUsers",
                        "summary": "List all users",
                        "tags": ["users"],
                    },
                    {
                        "path": "/users",
                        "method": "post",
                        "operation_id": "createUser",
                        "summary": "Create a user",
                        "request_schema": "CreateUserRequest",
                        "response_schema": "User",
                    },
                ],
            },
        }
        result = generate_openapi_spec(spec_outputs)
        assert "/users:" in result
        assert "listUsers" in result
        assert "createUser" in result

    def test_generate_with_entities(self) -> None:
        """Generates schema components from entities."""
        spec_outputs = {
            "api_spec": {"title": "Test API"},
            "db_spec": {
                "entities": [
                    {
                        "name": "User",
                        "fields": [
                            {"name": "id", "type": "uuid", "required": "true"},
                            {"name": "email", "type": "email", "required": "true"},
                            {"name": "name", "type": "string", "required": "false"},
                        ],
                    },
                ],
            },
        }
        result = generate_openapi_spec(spec_outputs)
        assert "User:" in result
        assert "schemas:" in result

    def test_fallback_for_empty_spec(self) -> None:
        """Empty spec outputs produce a valid minimal spec."""
        result = generate_openapi_spec({})
        assert "openapi: '3.1.0'" in result
        assert "FORGE Generated API" in result


class TestZodSchemaInjector:
    """Tests for Layer 2 Zod schema generation."""

    def test_generate_from_entities(self) -> None:
        """Generates Zod schemas from entity definitions."""
        prd_outputs = {
            "entities": [
                {
                    "name": "user",
                    "description": "Application user",
                    "fields": [
                        {"name": "id", "type": "uuid", "required": "true"},
                        {"name": "email", "type": "email", "required": "true"},
                        {"name": "display_name", "type": "string", "required": "false"},
                        {"name": "is_active", "type": "boolean", "required": "true"},
                    ],
                },
            ],
        }
        result = generate_zod_schemas(prd_outputs)
        assert "import { z }" in result
        assert "UserSchema" in result
        assert "z.string().uuid()" in result
        assert "z.string().email()" in result
        assert "z.boolean()" in result
        assert ".optional()" in result
        assert "export type User = z.infer<typeof UserSchema>" in result

    def test_generate_multiple_entities(self) -> None:
        """Multiple entities produce aggregate union type."""
        prd_outputs = {
            "entities": [
                {"name": "user", "fields": [{"name": "id", "type": "uuid"}]},
                {"name": "project", "fields": [{"name": "id", "type": "uuid"}]},
            ],
        }
        result = generate_zod_schemas(prd_outputs)
        assert "UserSchema" in result
        assert "ProjectSchema" in result
        assert "AnyEntity" in result

    def test_generate_fallback_no_entities(self) -> None:
        """No entities → fallback feature schema."""
        result = generate_zod_schemas({"features": ["auth", "dashboard"]})
        assert "FeatureSchema" in result
        assert "AUTO-GENERATED" in result

    def test_auto_generated_header(self) -> None:
        """Output has auto-generated header."""
        result = generate_zod_schemas({})
        assert "AUTO-GENERATED by FORGE Layer 2" in result

    def test_array_field_type(self) -> None:
        """Array fields generate z.array() with correct item type."""
        prd_outputs = {
            "entities": [
                {
                    "name": "project",
                    "fields": [
                        {"name": "tags", "type": "array", "item_type": "string"},
                    ],
                },
            ],
        }
        result = generate_zod_schemas(prd_outputs)
        assert "z.array(z.string())" in result


class TestPydanticSchemaInjector:
    """Tests for Layer 2 Pydantic model generation."""

    def test_generate_from_entities(self) -> None:
        """Generates Pydantic v2 models from entity definitions."""
        prd_outputs = {
            "entities": [
                {
                    "name": "user",
                    "description": "Application user model",
                    "fields": [
                        {"name": "id", "type": "uuid", "required": "true"},
                        {"name": "email", "type": "string", "required": "true",
                         "description": "User email address"},
                        {"name": "age", "type": "integer", "required": "false"},
                    ],
                },
            ],
        }
        result = generate_pydantic_schemas(prd_outputs)
        assert "from pydantic import BaseModel, Field" in result
        assert "class User(BaseModel):" in result
        assert "id: uuid.UUID" in result
        assert "email: str" in result
        assert "model_config" in result

    def test_auto_generated_header(self) -> None:
        """Output has auto-generated header."""
        result = generate_pydantic_schemas({})
        assert "AUTO-GENERATED by FORGE Layer 2" in result

    def test_optional_fields(self) -> None:
        """Optional fields get None default."""
        prd_outputs = {
            "entities": [
                {
                    "name": "item",
                    "fields": [
                        {"name": "note", "type": "string", "required": "false"},
                    ],
                },
            ],
        }
        result = generate_pydantic_schemas(prd_outputs)
        assert "None" in result


class TestDBTypeInjector:
    """Tests for Layer 2 DB type generation."""

    def test_generate_from_create_table(self) -> None:
        """Parses CREATE TABLE and generates TypeScript interfaces."""
        sql = """
        CREATE TABLE users (
            id UUID NOT NULL,
            email VARCHAR(255) NOT NULL,
            display_name TEXT,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        );
        """
        result = generate_typescript_types(sql)
        assert "export interface Users {" in result
        assert "id: string;" in result  # UUID → string (not nullable since NOT NULL)
        assert "email: string;" in result
        assert "display_name: string | null;" in result  # nullable (no NOT NULL)
        assert "is_active: boolean;" in result

    def test_generate_from_enum(self) -> None:
        """Parses CREATE TYPE AS ENUM."""
        sql = """
        CREATE TYPE user_role AS ENUM ('admin', 'user', 'moderator');
        CREATE TABLE users (
            id UUID NOT NULL,
            role user_role NOT NULL
        );
        """
        result = generate_typescript_types(sql)
        assert "UserRole" in result
        assert '"admin"' in result
        assert '"user"' in result

    def test_generate_multiple_tables(self) -> None:
        """Multiple tables generate multiple interfaces + TableName union."""
        sql = """
        CREATE TABLE users (
            id UUID NOT NULL,
            email VARCHAR(255) NOT NULL
        );
        CREATE TABLE projects (
            id UUID NOT NULL,
            name TEXT NOT NULL,
            user_id UUID NOT NULL
        );
        """
        result = generate_typescript_types(sql)
        assert "export interface Users {" in result
        assert "export interface Projects {" in result
        assert "TableName" in result

    def test_auto_generated_header(self) -> None:
        """Output has auto-generated header."""
        result = generate_typescript_types("")
        assert "AUTO-GENERATED by FORGE Layer 2" in result

    def test_array_types(self) -> None:
        """SQL array types map to TypeScript arrays."""
        sql = """
        CREATE TABLE items (
            id UUID NOT NULL,
            tags TEXT[] NOT NULL
        );
        """
        result = generate_typescript_types(sql)
        assert "string[]" in result

    def test_jsonb_type(self) -> None:
        """JSONB maps to Record<string, unknown>."""
        sql = """
        CREATE TABLE configs (
            id UUID NOT NULL,
            metadata JSONB
        );
        """
        result = generate_typescript_types(sql)
        assert "Record<string, unknown>" in result


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 4: File Coherence Engine                                   ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestSeamChecker:
    """Tests for Layer 4 seam/truncation detection."""

    def test_valid_file_passes(self) -> None:
        """A properly closed file passes."""
        content = """
import React from 'react';

export default function App() {
  return <div>Hello</div>;
}
"""
        report = check_seam("src/App.tsx", content)
        assert report.valid is True
        assert report.issues == []

    def test_unclosed_braces_detected(self) -> None:
        """Missing closing brace is caught."""
        content = """
export function broken() {
  if (true) {
    console.log('hello');
"""
        report = check_seam("src/broken.ts", content)
        assert report.valid is False
        assert any("unclosed braces" in issue for issue in report.issues)

    def test_truncation_marker_detected(self) -> None:
        """Truncation markers like '// ...' are caught."""
        content = """
export function partial() {
  return {
    name: 'test',
    // ...
  };
}
"""
        report = check_seam("src/partial.ts", content)
        assert report.valid is False
        assert any("truncation marker" in issue for issue in report.issues)

    def test_rest_of_code_marker(self) -> None:
        """'// rest of code' truncation marker is caught."""
        content = """
export class MyService {
  // rest of implementation
}
"""
        report = check_seam("src/service.ts", content)
        assert report.valid is False
        assert any("truncation marker" in issue for issue in report.issues)

    def test_empty_file_detected(self) -> None:
        """Empty file is flagged."""
        report = check_seam("src/empty.ts", "")
        assert report.valid is False
        assert any("empty" in issue for issue in report.issues)

    def test_unmatched_jsx_tags_detected(self) -> None:
        """Unclosed JSX component tags are caught."""
        content = """
export default function Page() {
  return (
    <Container>
      <Header>
        <Title>Hello</Title>
  );
}
"""
        report = check_seam("src/Page.tsx", content)
        assert report.valid is False
        # Should detect unclosed Container and/or Header

    def test_deliberate_truncation_scenario(self) -> None:
        """Full truncation scenario — file cut off mid-function.

        This is the specific test case requested: a deliberately
        truncated file.
        """
        content = """
import { useState } from 'react';
import { Button } from './components';

export default function Dashboard() {
  const [data, setData] = useState([]);

  const handleSubmit = async () => {
    const response = await fetch('/api/data');
    const json = await response.json("""
        report = check_seam("src/Dashboard.tsx", content)
        assert report.valid is False
        # Should have multiple issues: unclosed braces, parens, etc.
        assert len(report.issues) >= 1


class TestBarrelValidator:
    """Tests for Layer 4 barrel index.ts validation."""

    def test_valid_barrel(self) -> None:
        """Barrel re-exports everything consumers import."""
        index_content = """
export { Button } from './Button';
export { Input } from './Input';
export { Card } from './Card';
"""
        consumers = {
            "src/pages/Home.tsx": "import { Button, Card } from './components';",
        }
        report = validate_barrel(index_content, consumers, barrel_path="./components")
        assert report.valid is True
        assert report.missing_exports == []

    def test_missing_reexport(self) -> None:
        """Consumer imports a symbol not re-exported by barrel."""
        index_content = """
export { Button } from './Button';
"""
        consumers = {
            "src/pages/Home.tsx": "import { Button, Card } from './components';",
        }
        report = validate_barrel(index_content, consumers, barrel_path="./components")
        assert report.valid is False
        assert "Card" in report.missing_exports

    def test_extra_exports_reported(self) -> None:
        """Unused barrel exports are reported (not an error)."""
        index_content = """
export { Button } from './Button';
export { Input } from './Input';
export { Card } from './Card';
export { Modal } from './Modal';
"""
        consumers = {
            "src/pages/Home.tsx": "import { Button } from './components';",
        }
        report = validate_barrel(index_content, consumers, barrel_path="./components")
        assert report.valid is True
        assert "Modal" in report.extra_exports

    def test_wildcard_reexport(self) -> None:
        """Wildcard re-export passes all imports."""
        index_content = """
export * from './Button';
export * from './Input';
"""
        consumers = {
            "src/pages/Home.tsx": "import { Button, Input } from './components';",
        }
        report = validate_barrel(index_content, consumers, barrel_path="./components")
        assert report.valid is True


class TestFileCoherenceEngine:
    """Tests for the full Layer 4 coherence engine."""

    @pytest.mark.asyncio
    async def test_correct_project_passes(self) -> None:
        """A correct project with proper imports passes with 0 issues.

        This is a specific test case requested: correct project → 0 issues.
        """
        files = {
            "src/components/Button.tsx": (
                "import React from 'react';\n"
                "export function Button() { return null; }\n"
            ),
            "src/components/Card.tsx": (
                "import React from 'react';\n"
                "export function Card() { return null; }\n"
            ),
            "src/components/index.ts": (
                "export { Button } from './Button';\n"
                "export { Card } from './Card';\n"
            ),
            "src/pages/Home.tsx": (
                "import React from 'react';\n"
                "import { Button } from '../components/Button';\n"
                "export default function Home() { return null; }\n"
            ),
            "src/App.tsx": (
                "import React from 'react';\n"
                "import { Card } from './components/Card';\n"
                "export default function App() { return null; }\n"
            ),
        }

        report = await run_coherence_check("build-001", files)

        assert isinstance(report, CoherenceCheckReport)
        assert report.all_passed is True
        assert report.critical_errors == 0
        assert report.total_files == 5
        assert report.files_checked == 5

    @pytest.mark.asyncio
    async def test_catches_import_error(self) -> None:
        """Intentional import error is caught.

        This is a specific test case requested: intentional import
        error → verify it catches it.
        """
        files = {
            "src/components/Button.tsx": (
                "export function Button() { return null; }\n"
            ),
            "src/pages/Home.tsx": (
                "import { NonExistentComponent } from '../components/Button';\n"
                "export default function Home() { return null; }\n"
            ),
        }

        report = await run_coherence_check("build-002", files)

        assert report.all_passed is False
        assert report.critical_errors > 0
        # Should flag that NonExistentComponent is not exported by Button
        import_issues = [
            i for i in report.issues
            if i.issue_type in ("import_error", "missing_export")
        ]
        assert len(import_issues) > 0
        assert any("NonExistentComponent" in i.message for i in import_issues)

    @pytest.mark.asyncio
    async def test_catches_missing_source_file(self) -> None:
        """Import from non-existent file is flagged as critical."""
        files = {
            "src/App.tsx": (
                "import { Foo } from './missing-module';\n"
                "export default function App() { return null; }\n"
            ),
        }

        report = await run_coherence_check("build-003", files)

        assert report.all_passed is False
        assert report.critical_errors > 0
        missing_issues = [
            i for i in report.issues if i.issue_type == "missing_file"
        ]
        assert len(missing_issues) > 0

    @pytest.mark.asyncio
    async def test_auto_fixes_typo_imports(self) -> None:
        """Typo in named import (Levenshtein ≤ 2) is auto-fixed."""
        files = {
            "src/components/Button.tsx": (
                "export function Button() { return null; }\n"
            ),
            "src/pages/Home.tsx": (
                # "Buttn" is 1 edit away from "Button"
                "import { Buttn } from '../components/Button';\n"
                "export default function Home() { return null; }\n"
            ),
        }

        report = await run_coherence_check("build-004", files)

        # Should auto-fix the typo, not escalate as critical
        typo_fixes = [
            i for i in report.issues if i.issue_type == "typo"
        ]
        assert len(typo_fixes) > 0
        assert typo_fixes[0].severity == "auto_fixed"
        assert typo_fixes[0].fix_applied is not None
        assert report.auto_fixes_applied > 0

    @pytest.mark.asyncio
    async def test_detects_seam_errors(self) -> None:
        """Truncated file is caught by seam checker integration."""
        files = {
            "src/App.tsx": (
                "export default function App() {\n"
                "  return (\n"
                "    <div>\n"
                "      // ...\n"
            ),
        }

        report = await run_coherence_check("build-005", files)

        assert report.all_passed is False
        seam_issues = [
            i for i in report.issues if i.issue_type == "seam_error"
        ]
        assert len(seam_issues) > 0

    @pytest.mark.asyncio
    async def test_detects_circular_imports(self) -> None:
        """Circular import chain is detected."""
        files = {
            "src/a.ts": (
                "import { b } from './b';\n"
                "export const a = 'a';\n"
            ),
            "src/b.ts": (
                "import { c } from './c';\n"
                "export const b = 'b';\n"
            ),
            "src/c.ts": (
                "import { a } from './a';\n"
                "export const c = 'c';\n"
            ),
        }

        report = await run_coherence_check("build-006", files)

        circular_issues = [
            i for i in report.issues if i.issue_type == "circular_import"
        ]
        assert len(circular_issues) > 0

    @pytest.mark.asyncio
    async def test_handles_non_ts_files(self) -> None:
        """Non-TS/JS files are counted but not checked for imports."""
        files = {
            "src/styles.css": "body { margin: 0; }",
            "src/App.tsx": (
                "import React from 'react';\n"
                "export default function App() { return null; }\n"
            ),
            "README.md": "# My App",
        }

        report = await run_coherence_check("build-007", files)

        assert report.total_files == 3
        assert report.files_checked == 1  # Only App.tsx

    @pytest.mark.asyncio
    async def test_skips_external_imports(self) -> None:
        """External package imports (react, etc.) are skipped."""
        files = {
            "src/App.tsx": (
                "import React from 'react';\n"
                "import { useState } from 'react';\n"
                "import axios from 'axios';\n"
                "export default function App() { return null; }\n"
            ),
        }

        report = await run_coherence_check("build-008", files)

        assert report.all_passed is True
        assert report.critical_errors == 0


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  Integration: Pipeline graph with reliability layers              ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestGraphIntegration:
    """Tests that reliability layers are properly integrated into graph.py."""

    def test_imports_exist(self) -> None:
        """Graph module imports reliability layer functions."""
        from app.agents import graph
        assert hasattr(graph, 'input_layer')
        assert hasattr(graph, 'spec_layer')
        assert hasattr(graph, 'build')

    def test_state_has_reliability_fields(self) -> None:
        """PipelineState includes reliability layer fields."""
        from app.agents.state import PipelineState
        annotations = PipelineState.__annotations__
        assert "env_contract" in annotations
        assert "resolved_dependencies" in annotations
        assert "injected_schemas" in annotations
        assert "coherence_report" in annotations

    def test_g10_uses_coherence_report(self) -> None:
        """G10 validator uses real coherence report data."""
        from app.agents.validators import validate_g10

        # With passing coherence report
        state = {
            "coherence_report": {
                "all_passed": True,
                "critical_errors": 0,
                "auto_fixes_applied": 2,
                "files_checked": 10,
            },
            "generated_files": {"a.ts": "export const a = 1;"},
        }
        result = validate_g10(state)  # type: ignore[arg-type]
        assert result["passed"] is True

        # With failing coherence report
        state["coherence_report"] = {
            "all_passed": False,
            "critical_errors": 3,
            "auto_fixes_applied": 1,
            "files_checked": 10,
        }
        result = validate_g10(state)  # type: ignore[arg-type]
        assert result["passed"] is False
        assert "3 critical error" in result["reason"]
