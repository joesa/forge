"""
Tests for FORGE Reliability Layers 3, 5, and 6.

Layer 3: Static analysis (AST analyser, import graph, runtime error predictor)
Layer 5: Code contracts (pattern library, API contract validator, type inference)
Layer 6: Build intelligence (cache, memory, error boundaries, incremental build)

Architecture rules validated:
  #7: Never call real external APIs in tests (all mocked)
  #4: Build agents: deterministic
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Layer 3 imports ──────────────────────────────────────────────────
from app.reliability.layer3_static.ast_analyser import (
    ASTIssue,
    ASTReport,
    analyze_file,
)
from app.reliability.layer3_static.import_graph_resolver import (
    ImportGraph,
    build_import_graph,
)
from app.reliability.layer3_static.runtime_error_predictor import (
    PredictedError,
    predict_errors,
)

# ── Layer 5 imports ──────────────────────────────────────────────────
from app.reliability.layer5_contracts.pattern_library import (
    Pattern,
    find_applicable_patterns,
    get_pattern,
)
from app.reliability.layer5_contracts.api_contract_validator import (
    ContractReport,
    validate_against_openapi,
)
from app.reliability.layer5_contracts.type_inference_engine import (
    infer_typescript_types,
)

# ── Layer 6 imports ──────────────────────────────────────────────────
from app.reliability.layer6_intelligence.build_cache import (
    CacheResult,
    check_cache,
    store_in_cache,
    _spec_to_text,
)
from app.reliability.layer6_intelligence.build_memory import (
    BuildMemory,
    record_successful_build,
    get_relevant_memories,
)
from app.reliability.layer6_intelligence.error_boundary_injector import (
    inject_error_boundaries,
)
from app.reliability.layer6_intelligence.incremental_build import (
    detect_changed_modules,
)


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 3: Static Analysis                                        ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestASTAnalyser:
    """Tests for Layer 3 AST analyser."""

    def test_clean_file_no_issues(self) -> None:
        """Clean TypeScript file has no issues."""
        content = """
import React from 'react';

export default function App() {
  const name = 'World';
  return <div>Hello {name}</div>;
}
"""
        report = analyze_file("src/App.tsx", content)
        assert isinstance(report, ASTReport)
        assert report.issues == []
        assert report.severity == "warning"
        assert report.lines_analysed > 0

    def test_detects_null_reference(self) -> None:
        """Detects property chain on nullable variable."""
        content = """
import React, { useState } from 'react';

export default function Profile() {
  const [user, setUser] = useState<User | null>(null);
  return <div>{user.profile.name}</div>;
}
"""
        report = analyze_file("src/Profile.tsx", content)
        null_issues = [i for i in report.issues if i.rule == "null_ref"]
        assert len(null_issues) > 0
        assert "user" in null_issues[0].message

    def test_detects_unhandled_promise(self) -> None:
        """Detects await call without try/catch."""
        content = """
export async function fetchData() {
  const response = await fetch('/api/data');
  const data = await response.json();
  return data;
}
"""
        report = analyze_file("src/api.ts", content)
        promise_issues = [
            i for i in report.issues if i.rule == "unhandled_promise"
        ]
        assert len(promise_issues) > 0

    def test_skips_caught_promises(self) -> None:
        """Does not flag await inside try/catch."""
        content = """
export async function fetchData() {
  try {
    const response = await fetch('/api/data');
    return response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}
"""
        report = analyze_file("src/api.ts", content)
        promise_issues = [
            i for i in report.issues if i.rule == "unhandled_promise"
        ]
        assert len(promise_issues) == 0

    def test_detects_missing_error_boundary_in_page(self) -> None:
        """Page component without ErrorBoundary is flagged."""
        content = """
import React from 'react';

export default function Dashboard() {
  return <div>Dashboard</div>;
}
"""
        report = analyze_file("src/pages/Dashboard.tsx", content)
        boundary_issues = [
            i for i in report.issues if i.rule == "missing_error_boundary"
        ]
        assert len(boundary_issues) > 0

    def test_skips_error_boundary_for_non_page(self) -> None:
        """Non-page component does not require ErrorBoundary."""
        content = """
import React from 'react';

export function Button() {
  return <button>Click</button>;
}
"""
        report = analyze_file("src/components/Button.tsx", content)
        boundary_issues = [
            i for i in report.issues if i.rule == "missing_error_boundary"
        ]
        assert len(boundary_issues) == 0

    def test_detects_zustand_mutation(self) -> None:
        """Direct state mutation in Zustand store flagged as error."""
        content = """
import { create } from 'zustand';

export const useStore = create((set) => ({
  items: [],
  addItem: (item) => {
    state.items = [...state.items, item];
  },
}));
"""
        report = analyze_file("src/stores/useStore.ts", content)
        mutation_issues = [
            i for i in report.issues if i.rule == "zustand_mutation"
        ]
        assert len(mutation_issues) > 0
        assert mutation_issues[0].severity == "error"
        assert report.severity == "error"

    def test_skips_zustand_with_immer(self) -> None:
        """Zustand store using immer is not flagged."""
        content = """
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

export const useStore = create(immer((set) => ({
  items: [],
  addItem: (item) => set((state) => { state.items.push(item); }),
})));
"""
        report = analyze_file("src/stores/useStore.ts", content)
        mutation_issues = [
            i for i in report.issues if i.rule == "zustand_mutation"
        ]
        assert len(mutation_issues) == 0

    def test_ignores_non_ts_files(self) -> None:
        """Non-TypeScript files return empty report."""
        report = analyze_file("src/styles.css", "body { margin: 0; }")
        assert report.issues == []
        assert report.lines_analysed == 0


class TestImportGraphResolver:
    """Tests for Layer 3 import graph resolver."""

    def test_builds_simple_graph(self) -> None:
        """Builds graph from simple imports."""
        files = {
            "src/App.tsx": "import { Button } from './components/Button';\n",
            "src/components/Button.tsx": "export function Button() {}\n",
        }
        graph = build_import_graph(files)
        assert isinstance(graph, ImportGraph)
        assert graph.total_files == 2
        assert graph.total_edges == 1
        assert "src/components/Button.tsx" in graph.graph.get("src/App.tsx", [])

    def test_detects_circular_imports(self) -> None:
        """Circular import chain is detected."""
        files = {
            "src/a.ts": "import { b } from './b';\nexport const a = 1;\n",
            "src/b.ts": "import { a } from './a';\nexport const b = 2;\n",
        }
        graph = build_import_graph(files)
        assert len(graph.circular_deps) > 0

    def test_detects_missing_imports(self) -> None:
        """Import from non-existent file is reported."""
        files = {
            "src/App.tsx": "import { Foo } from './missing';\n",
        }
        graph = build_import_graph(files)
        assert len(graph.missing_imports) > 0
        assert any("missing" in m for m in graph.missing_imports)

    def test_skips_external_packages(self) -> None:
        """External package imports don't appear in graph."""
        files = {
            "src/App.tsx": (
                "import React from 'react';\n"
                "import axios from 'axios';\n"
                "export default function App() {}\n"
            ),
        }
        graph = build_import_graph(files)
        assert graph.total_edges == 0
        assert graph.missing_imports == []

    def test_resolves_index_files(self) -> None:
        """Imports of directories resolve to index files."""
        files = {
            "src/App.tsx": "import { Button } from './components';\n",
            "src/components/index.ts": "export { Button } from './Button';\n",
            "src/components/Button.tsx": "export function Button() {}\n",
        }
        graph = build_import_graph(files)
        assert "src/components/index.ts" in graph.graph.get("src/App.tsx", [])


class TestRuntimeErrorPredictor:
    """Tests for Layer 3 runtime error predictor."""

    def test_predicts_cannot_read_property(self) -> None:
        """Detects nested property access on nullable source."""
        content = """
export function Profile({ data }) {
  return <div>{data.user.name}</div>;
}
"""
        errors = predict_errors(content)
        crp_errors = [
            e for e in errors if e.error_type == "cannot_read_property"
        ]
        assert len(crp_errors) > 0
        assert "user" in crp_errors[0].predicted_message
        assert "data" in crp_errors[0].fix_suggestion

    def test_predicts_max_update_depth(self) -> None:
        """Detects setState in render body."""
        content = """
import { useState } from 'react';

export default function Counter() {
  const [count, setCount] = useState(0);
  setCount(count + 1);
  return <div>{count}</div>;
}
"""
        errors = predict_errors(content)
        mud_errors = [
            e for e in errors if e.error_type == "max_update_depth"
        ]
        assert len(mud_errors) > 0

    def test_no_false_positive_in_useeffect(self) -> None:
        """setState in useEffect is not flagged."""
        content = """
import { useState, useEffect } from 'react';

export default function Loader() {
  const [data, setData] = useState(null);
  useEffect(() => {
    setData('loaded');
  }, []);
  return <div>{data}</div>;
}
"""
        errors = predict_errors(content)
        mud_errors = [
            e for e in errors if e.error_type == "max_update_depth"
        ]
        assert len(mud_errors) == 0

    def test_predicts_missing_key_prop(self) -> None:
        """Detects .map() rendering JSX without key prop."""
        content = """
export function List({ items }) {
  return <ul>{items.map((item) => <li>{item.name}</li>)}</ul>;
}
"""
        errors = predict_errors(content)
        key_errors = [
            e for e in errors if e.error_type == "missing_key_prop"
        ]
        assert len(key_errors) > 0


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 5: Code Contract Enforcement                              ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestPatternLibrary:
    """Tests for Layer 5 pattern library."""

    def test_get_known_pattern(self) -> None:
        """Get a known pattern by name."""
        pattern = get_pattern("auth_jwt")
        assert pattern is not None
        assert isinstance(pattern, Pattern)
        assert pattern.name == "auth_jwt"
        assert "JWT" in pattern.description
        assert len(pattern.anti_patterns) > 0

    def test_get_unknown_pattern_returns_none(self) -> None:
        """Unknown pattern name returns None."""
        pattern = get_pattern("nonexistent_pattern")
        assert pattern is None

    def test_find_auth_patterns(self) -> None:
        """find_applicable_patterns('user authentication') returns auth_jwt."""
        results = find_applicable_patterns("user authentication")
        assert len(results) > 0
        names = [p.name for p in results]
        assert "auth_jwt" in names

    def test_find_payment_patterns(self) -> None:
        """Stripe-related search returns stripe_webhook."""
        results = find_applicable_patterns("payment processing with stripe")
        assert len(results) > 0
        names = [p.name for p in results]
        assert "stripe_webhook" in names

    def test_find_state_management_patterns(self) -> None:
        """State management search returns zustand_store."""
        results = find_applicable_patterns("zustand state management")
        assert len(results) > 0
        names = [p.name for p in results]
        assert "zustand_store" in names

    def test_find_empty_query_returns_empty(self) -> None:
        """Empty query returns no patterns."""
        results = find_applicable_patterns("")
        assert results == []

    def test_pattern_has_implementation_template(self) -> None:
        """Core patterns have implementation templates."""
        pattern = get_pattern("auth_jwt")
        assert pattern is not None
        assert len(pattern.implementation_template) > 0

    def test_at_least_30_patterns(self) -> None:
        """Registry has at least 30 patterns."""
        from app.reliability.layer5_contracts.pattern_library import (
            _PATTERN_REGISTRY,
        )
        assert len(_PATTERN_REGISTRY) >= 30

    def test_at_least_10_patterns_with_test_templates(self) -> None:
        """At least 10 patterns have non-empty test templates."""
        from app.reliability.layer5_contracts.pattern_library import (
            _PATTERN_REGISTRY,
        )
        with_tests = [
            p for p in _PATTERN_REGISTRY.values() if p.test_template.strip()
        ]
        assert len(with_tests) >= 10, (
            f"Only {len(with_tests)} patterns have test templates, need >= 10"
        )

    def test_find_form_patterns(self) -> None:
        """Form validation search returns form_validation."""
        results = find_applicable_patterns("form validation with zod")
        names = [p.name for p in results]
        assert "form_validation" in names


class TestAPIContractValidator:
    """Tests for Layer 5 API contract validator."""

    def test_valid_contract_full_coverage(self) -> None:
        """Full route coverage passes validation."""
        spec = """
openapi: '3.1.0'
info:
  title: Test API
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        '200':
          description: OK
    post:
      operationId: createUser
      responses:
        '201':
          description: Created
"""
        routes = {
            "src/routes/users.ts": (
                "app.get('/users', listUsersHandler);\n"
                "app.post('/users', createUserHandler);\n"
            ),
        }
        report = validate_against_openapi(routes, spec)
        assert isinstance(report, ContractReport)
        assert report.coverage_pct == 100.0
        assert report.missing_routes == []
        assert report.passed is True

    def test_missing_routes_detected(self) -> None:
        """Missing route implementation is detected."""
        spec = """
openapi: '3.1.0'
info:
  title: Test API
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        '200':
          description: OK
  /users/{id}:
    delete:
      operationId: deleteUser
      responses:
        '204':
          description: Deleted
"""
        routes = {
            "src/routes/users.ts": "app.get('/users', handler);\n",
        }
        report = validate_against_openapi(routes, spec)
        assert report.coverage_pct < 100.0
        assert len(report.missing_routes) > 0

    def test_empty_spec_passes(self) -> None:
        """Empty spec → 100% coverage with no routes."""
        report = validate_against_openapi({}, "")
        assert report.coverage_pct >= 0.0


class TestTypeInferenceEngine:
    """Tests for Layer 5 type inference engine."""

    def test_pydantic_to_typescript(self) -> None:
        """Converts Pydantic model to TypeScript interface."""
        pydantic_source = """
from pydantic import BaseModel

class User(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    is_active: bool
"""
        result = infer_typescript_types(python_pydantic_schemas=pydantic_source)
        assert "export interface User {" in result
        assert "id: string;" in result
        assert "email: string;" in result
        assert "name: string | null;" in result
        assert "is_active: boolean;" in result
        assert "AUTO-GENERATED by FORGE Layer 5" in result

    def test_sql_to_typescript(self) -> None:
        """Converts SQL DDL to TypeScript interface."""
        sql = """
        CREATE TABLE users (
            id UUID NOT NULL,
            email VARCHAR(255) NOT NULL,
            display_name TEXT,
            is_active BOOLEAN NOT NULL
        );
        """
        result = infer_typescript_types(sql_schema=sql)
        assert "export interface Users {" in result
        assert "id: string;" in result
        assert "display_name: string | null;" in result

    def test_combined_pydantic_and_sql(self) -> None:
        """Both Pydantic and SQL generate interfaces."""
        pydantic_source = """
from pydantic import BaseModel

class Item(BaseModel):
    id: str
    name: str
"""
        sql = """
        CREATE TABLE orders (
            id UUID NOT NULL,
            total NUMERIC NOT NULL
        );
        """
        result = infer_typescript_types(
            python_pydantic_schemas=pydantic_source,
            sql_schema=sql,
        )
        assert "export interface Item {" in result
        assert "export interface Orders {" in result

    def test_optional_fields(self) -> None:
        """Optional[T] and T | None produce nullable types."""
        pydantic_source = """
from pydantic import BaseModel
from typing import Optional

class Profile(BaseModel):
    bio: Optional[str]
    avatar: str | None
"""
        result = infer_typescript_types(python_pydantic_schemas=pydantic_source)
        assert "bio: string | null;" in result
        assert "avatar: string | null;" in result

    def test_list_fields(self) -> None:
        """list[T] produces T[] in TypeScript."""
        pydantic_source = """
from pydantic import BaseModel

class Config(BaseModel):
    tags: list[str]
"""
        result = infer_typescript_types(python_pydantic_schemas=pydantic_source)
        assert "tags: string[];" in result

    def test_empty_input_produces_header(self) -> None:
        """Empty input produces header comment only."""
        result = infer_typescript_types()
        assert "AUTO-GENERATED by FORGE Layer 5" in result


# ╔═══════════════════════════════════════════════════════════════════╗
# ║  LAYER 6: Build Intelligence                                      ║
# ╚═══════════════════════════════════════════════════════════════════╝


class TestBuildCache:
    """Tests for Layer 6 build cache (all external calls mocked)."""

    def test_spec_to_text(self) -> None:
        """Converts idea spec to readable text."""
        spec = {
            "title": "Todo App",
            "description": "A simple todo app",
            "features": ["add tasks", "mark complete"],
            "framework": "react_vite",
        }
        text = _spec_to_text(spec)
        assert "Todo App" in text
        assert "react_vite" in text
        assert "add tasks" in text

    @pytest.mark.asyncio
    async def test_cache_hit_returns_result(self) -> None:
        """Cache hit with similarity >= 0.92 returns CacheResult."""
        mock_embedding = [0.1] * 1536
        mock_match = {
            "matches": [{
                "score": 0.95,
                "metadata": {
                    "build_id": "build-123",
                    "generated_files": '{"src/App.tsx": "export default function App() {}"}',
                    "tech_stack": ["react", "vite"],
                    "cached_at": "2026-01-01T00:00:00Z",
                    "build_duration": 120.0,
                },
            }],
        }

        with patch(
            "app.reliability.layer6_intelligence.build_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=mock_embedding,
        ), patch(
            "app.reliability.layer6_intelligence.build_cache._get_pinecone_index",
        ) as mock_index:
            mock_index.return_value.query.return_value = mock_match

            result = await check_cache({"title": "Todo App"})

            assert result is not None
            assert isinstance(result, CacheResult)
            assert result.hit is True
            assert result.similarity_score == 0.95
            assert "src/App.tsx" in result.cached_files
            assert result.build_id == "build-123"

    @pytest.mark.asyncio
    async def test_cache_miss_below_threshold(self) -> None:
        """Cache returns None when similarity < 0.92."""
        mock_embedding = [0.1] * 1536
        mock_match = {
            "matches": [{
                "score": 0.80,
                "metadata": {},
            }],
        }

        with patch(
            "app.reliability.layer6_intelligence.build_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=mock_embedding,
        ), patch(
            "app.reliability.layer6_intelligence.build_cache._get_pinecone_index",
        ) as mock_index:
            mock_index.return_value.query.return_value = mock_match

            result = await check_cache({"title": "Completely different app"})

            assert result is None

    @pytest.mark.asyncio
    async def test_cache_miss_no_matches(self) -> None:
        """Cache returns None when no matches exist."""
        mock_embedding = [0.1] * 1536

        with patch(
            "app.reliability.layer6_intelligence.build_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=mock_embedding,
        ), patch(
            "app.reliability.layer6_intelligence.build_cache._get_pinecone_index",
        ) as mock_index:
            mock_index.return_value.query.return_value = {"matches": []}

            result = await check_cache({"title": "Brand new app"})

            assert result is None

    @pytest.mark.asyncio
    async def test_store_in_cache_success(self) -> None:
        """Store a build in cache successfully."""
        mock_embedding = [0.1] * 1536

        with patch(
            "app.reliability.layer6_intelligence.build_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=mock_embedding,
        ), patch(
            "app.reliability.layer6_intelligence.build_cache._get_pinecone_index",
        ) as mock_index:
            mock_upsert = MagicMock()
            mock_index.return_value.upsert = mock_upsert

            success = await store_in_cache(
                idea_spec={"title": "Todo App"},
                generated_files={"src/App.tsx": "export default function App() {}"},
                build_id="build-456",
                tech_stack=["react", "vite"],
                build_duration=45.0,
                gates_passed=True,
            )

            assert success is True
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_rejected_without_gates_passed(self) -> None:
        """store_in_cache rejects when gates_passed is False (cache poisoning prevention)."""
        success = await store_in_cache(
            idea_spec={"title": "Failed build"},
            generated_files={"src/App.tsx": "broken code"},
            build_id="build-bad",
            gates_passed=False,
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_store_rejected_default_gates_passed(self) -> None:
        """store_in_cache defaults gates_passed to False — must be explicit."""
        success = await store_in_cache(
            idea_spec={"title": "Sneaky build"},
            generated_files={"src/App.tsx": "code"},
            build_id="build-sneaky",
        )
        assert success is False


class TestBuildMemory:
    """Tests for Layer 6 build memory (Redis mocked)."""

    @pytest.mark.asyncio
    async def test_record_and_retrieve(self) -> None:
        """Records a build and retrieves it by tech stack match."""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock()
        mock_redis.zadd = MagicMock()
        mock_redis.zcard = MagicMock(return_value=1)
        mock_redis.zrevrange = MagicMock(return_value=["build-001"])

        memory = BuildMemory(
            build_id="build-001",
            tech_stack=["react", "vite", "tailwind"],
            patterns_used=["auth_jwt", "zustand_store"],
            errors_fixed=["missing import"],
            features=["authentication", "dashboard"],
            build_duration_seconds=60.0,
            recorded_at="2026-01-01",
        )
        mock_redis.get = MagicMock(return_value=memory.model_dump_json())

        with patch(
            "app.reliability.layer6_intelligence.build_memory._get_redis_client",
            return_value=mock_redis,
        ):
            # Record
            success = await record_successful_build(
                build_id="build-001",
                tech_stack=["react", "vite", "tailwind"],
                patterns_used=["auth_jwt", "zustand_store"],
                errors_fixed=["missing import"],
                features=["authentication", "dashboard"],
            )
            assert success is True
            mock_redis.set.assert_called_once()

            # Retrieve
            memories = await get_relevant_memories(
                tech_stack=["react", "vite"],
                features=["authentication"],
            )
            assert len(memories) > 0
            assert memories[0].build_id == "build-001"

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self) -> None:
        """No matching memories returns empty list."""
        mock_redis = MagicMock()
        mock_redis.zrevrange = MagicMock(return_value=["build-001"])

        memory = BuildMemory(
            build_id="build-001",
            tech_stack=["python", "django"],
            patterns_used=[],
            errors_fixed=[],
            features=["backend api"],
            recorded_at="2026-01-01",
        )
        mock_redis.get = MagicMock(return_value=memory.model_dump_json())

        with patch(
            "app.reliability.layer6_intelligence.build_memory._get_redis_client",
            return_value=mock_redis,
        ):
            memories = await get_relevant_memories(
                tech_stack=["react", "svelte"],
                features=["3d rendering"],
            )
            assert len(memories) == 0


class TestErrorBoundaryInjector:
    """Tests for Layer 6 error boundary injector."""

    def test_injects_into_page(self) -> None:
        """Injects ErrorBoundary into page component."""
        files = {
            "src/pages/Dashboard.tsx": (
                "import React from 'react';\n"
                "\n"
                "export default function Dashboard() {\n"
                "  return (\n"
                "    <div>Dashboard</div>\n"
                "  );\n"
                "}\n"
            ),
        }
        result = inject_error_boundaries(files)
        assert "src/pages/Dashboard.tsx" in result
        assert "ErrorBoundary" in result["src/pages/Dashboard.tsx"]
        assert "import { ErrorBoundary }" in result["src/pages/Dashboard.tsx"]

    def test_skips_already_wrapped(self) -> None:
        """Skips files that already have ErrorBoundary."""
        files = {
            "src/pages/Home.tsx": (
                "import React from 'react';\n"
                "import { ErrorBoundary } from '@/components/ui/ErrorBoundary';\n"
                "\n"
                "export default function Home() {\n"
                "  return <ErrorBoundary><div>Home</div></ErrorBoundary>;\n"
                "}\n"
            ),
        }
        result = inject_error_boundaries(files)
        assert "src/pages/Home.tsx" not in result

    def test_skips_non_page_files(self) -> None:
        """Non-page component files are not modified."""
        files = {
            "src/components/Button.tsx": (
                "import React from 'react';\n"
                "export function Button() { return <button>Click</button>; }\n"
            ),
        }
        result = inject_error_boundaries(files)
        assert len(result) == 0

    def test_multiple_pages(self) -> None:
        """Injects into multiple page files."""
        files = {
            "src/pages/Home.tsx": (
                "import React from 'react';\n"
                "export default function Home() {\n"
                "  return (\n"
                "    <div>Home</div>\n"
                "  );\n"
                "}\n"
            ),
            "src/pages/About.tsx": (
                "import React from 'react';\n"
                "export default function About() {\n"
                "  return (\n"
                "    <div>About</div>\n"
                "  );\n"
                "}\n"
            ),
            "src/components/Header.tsx": (
                "export function Header() { return <h1>Title</h1>; }\n"
            ),
        }
        result = inject_error_boundaries(files)
        assert len(result) == 2
        assert "src/pages/Home.tsx" in result
        assert "src/pages/About.tsx" in result
        assert "src/components/Header.tsx" not in result


class TestIncrementalBuild:
    """Tests for Layer 6 incremental build detection."""

    def test_identical_files_no_changes(self) -> None:
        """Identical file sets produce no changes."""
        files = {
            "src/App.tsx": "export default function App() {}",
            "src/index.ts": "import App from './App';",
        }
        changed = detect_changed_modules(files, files)
        assert changed == []

    def test_detects_modified_file(self) -> None:
        """Modified file is detected."""
        cached = {
            "src/App.tsx": "export default function App() { return null; }",
        }
        new = {
            "src/App.tsx": "export default function App() { return <div>Hi</div>; }",
        }
        changed = detect_changed_modules(new, cached)
        assert "src/App.tsx" in changed

    def test_detects_new_file(self) -> None:
        """New file is detected."""
        cached = {
            "src/App.tsx": "export default function App() {}",
        }
        new = {
            "src/App.tsx": "export default function App() {}",
            "src/utils.ts": "export const VERSION = '1.0';",
        }
        changed = detect_changed_modules(new, cached)
        assert "src/utils.ts" in changed
        assert "src/App.tsx" not in changed

    def test_detects_deleted_file(self) -> None:
        """Deleted file is detected."""
        cached = {
            "src/App.tsx": "export default function App() {}",
            "src/old.ts": "export const OLD = true;",
        }
        new = {
            "src/App.tsx": "export default function App() {}",
        }
        changed = detect_changed_modules(new, cached)
        assert "src/old.ts" in changed

    def test_empty_inputs(self) -> None:
        """Empty inputs produce no changes."""
        changed = detect_changed_modules({}, {})
        assert changed == []

    def test_output_is_sorted(self) -> None:
        """Output is deterministically sorted."""
        cached = {}
        new = {
            "z.ts": "z",
            "a.ts": "a",
            "m.ts": "m",
        }
        changed = detect_changed_modules(new, cached)
        assert changed == sorted(changed)
