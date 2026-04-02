"""
Component Agent (Agent 3) — generates shared UI components.

Layer 2 inject: Zod schemas + TypeScript interfaces.
Files: components/ui/ — Button, Input, Select, Textarea, Card, Modal,
  Toast, Badge, Spinner, Avatar, Divider, EmptyState, ErrorBoundary
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)

AGENT_NAME = "component"

_SYSTEM_PROMPT = """You are a senior UI engineer generating a reusable component library.
Generate TypeScript React components with proper typing, prop interfaces,
forward refs, and accessibility attributes.

Return a JSON object where keys are file paths and values are file contents.
Each component: own file, explicit TS interface, forwardRef, ARIA, Tailwind CSS.
Include an index.ts barrel file that re-exports everything."""

# ── Component templates ──────────────────────────────────────────────
# Each tuple: (filename, component_name, is_class_component)

_COMPONENT_NAMES = [
    "Button", "Input", "Select", "Textarea", "Card", "Modal",
    "Toast", "Badge", "Spinner", "Avatar", "Divider", "EmptyState",
    "ErrorBoundary",
]


def _gen_button() -> str:
    return '''import React from 'react';
import Spinner from './Spinner';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

const variants: Record<string, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700',
  secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
  outline: 'border border-gray-300 hover:bg-gray-50',
  ghost: 'hover:bg-gray-100',
  danger: 'bg-red-600 text-white hover:bg-red-700',
};
const sizes: Record<string, string> = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4', lg: 'h-12 px-6 text-lg' };

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, className, children, disabled, ...props }, ref) => (
    <button ref={ref} className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:ring-2 disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className ?? ''}`} disabled={disabled || isLoading} {...props}>
      {isLoading ? <Spinner size="sm" /> : null}{children}
    </button>
  )
);
Button.displayName = 'Button';
export type { ButtonProps };
export default Button;
'''


def _gen_input() -> str:
    return '''import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\\s+/g, '-');
    return (
      <div className="flex flex-col gap-1">
        {label && <label htmlFor={inputId} className="text-sm font-medium">{label}</label>}
        <input ref={ref} id={inputId} className={`h-11 rounded-lg border px-3 text-sm ${error ? 'border-red-500' : 'border-gray-300'} ${className ?? ''}`} aria-invalid={!!error} {...props} />
        {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
        {helperText && !error && <p className="text-xs text-gray-500">{helperText}</p>}
      </div>
    );
  }
);
Input.displayName = 'Input';
export type { InputProps };
export default Input;
'''


def _gen_simple(name: str, props: str, body: str) -> str:
    return f"import React from 'react';\n\n{props}\n\n{body}\n\nexport type {{ {name}Props }};\nexport default {name};\n"


def _build_default_components(state: PipelineState) -> dict[str, str]:
    """Build deterministic default shared UI components."""
    files: dict[str, str] = {}

    files["src/components/ui/Button.tsx"] = _gen_button()
    files["src/components/ui/Input.tsx"] = _gen_input()

    files["src/components/ui/Select.tsx"] = _gen_simple("Select",
        "interface SelectOption { value: string; label: string; }\ninterface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> { label?: string; error?: string; options: SelectOption[]; placeholder?: string; }",
        "const Select = React.forwardRef<HTMLSelectElement, SelectProps>(\n  ({ label, error, options, placeholder, className, ...props }, ref) => (\n    <div className=\"flex flex-col gap-1\">\n      {label && <label className=\"text-sm font-medium\">{label}</label>}\n      <select ref={ref} className={`h-11 rounded-lg border px-3 ${className ?? ''}`} {...props}>\n        {placeholder && <option value=\"\">{placeholder}</option>}\n        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}\n      </select>\n      {error && <p className=\"text-xs text-red-600\" role=\"alert\">{error}</p>}\n    </div>\n  )\n);\nSelect.displayName = 'Select';")

    files["src/components/ui/Textarea.tsx"] = _gen_simple("Textarea",
        "interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> { label?: string; error?: string; }",
        "const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(\n  ({ label, error, className, ...props }, ref) => (\n    <div className=\"flex flex-col gap-1\">\n      {label && <label className=\"text-sm font-medium\">{label}</label>}\n      <textarea ref={ref} className={`rounded-lg border px-3 py-2 min-h-[80px] ${className ?? ''}`} {...props} />\n      {error && <p className=\"text-xs text-red-600\" role=\"alert\">{error}</p>}\n    </div>\n  )\n);\nTextarea.displayName = 'Textarea';")

    files["src/components/ui/Card.tsx"] = _gen_simple("Card",
        "interface CardProps { children: React.ReactNode; className?: string; padding?: 'none' | 'sm' | 'md' | 'lg'; }",
        "const pad: Record<string, string> = { none: '', sm: 'p-3', md: 'p-5', lg: 'p-7' };\nfunction Card({ children, className, padding = 'md' }: CardProps) {\n  return <div className={`rounded-xl border bg-white shadow-sm ${pad[padding]} ${className ?? ''}`}>{children}</div>;\n}")

    files["src/components/ui/Modal.tsx"] = _gen_simple("Modal",
        "interface ModalProps { isOpen: boolean; onClose: () => void; title?: string; children: React.ReactNode; }",
        "function Modal({ isOpen, onClose, title, children }: ModalProps) {\n  if (!isOpen) return null;\n  return (\n    <div className=\"fixed inset-0 z-50 flex items-center justify-center\" role=\"dialog\" aria-modal=\"true\">\n      <div className=\"fixed inset-0 bg-black/50\" onClick={onClose} />\n      <div className=\"relative z-10 rounded-xl bg-white p-6 shadow-xl max-w-md\">\n        {title && <h2 className=\"mb-4 text-lg font-semibold\">{title}</h2>}\n        {children}\n      </div>\n    </div>\n  );\n}")

    files["src/components/ui/Toast.tsx"] = _gen_simple("Toast",
        "interface ToastProps { message: string; type?: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean; onClose: () => void; }",
        "const styles: Record<string, string> = { success: 'bg-green-50 border-green-200', error: 'bg-red-50 border-red-200', warning: 'bg-yellow-50 border-yellow-200', info: 'bg-blue-50 border-blue-200' };\nfunction Toast({ message, type = 'info', isVisible, onClose }: ToastProps) {\n  if (!isVisible) return null;\n  return <div className={`fixed bottom-4 right-4 z-50 rounded-lg border p-4 shadow-lg ${styles[type]}`} role=\"alert\"><span>{message}</span><button onClick={onClose} aria-label=\"Close\">&times;</button></div>;\n}")

    files["src/components/ui/Badge.tsx"] = _gen_simple("Badge",
        "interface BadgeProps { children: React.ReactNode; variant?: 'default' | 'success' | 'warning' | 'danger'; className?: string; }",
        "const v: Record<string, string> = { default: 'bg-gray-100', success: 'bg-green-100', warning: 'bg-yellow-100', danger: 'bg-red-100' };\nfunction Badge({ children, variant = 'default', className }: BadgeProps) {\n  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${v[variant]} ${className ?? ''}`}>{children}</span>;\n}")

    files["src/components/ui/Spinner.tsx"] = _gen_simple("Spinner",
        "interface SpinnerProps { size?: 'sm' | 'md' | 'lg'; className?: string; }",
        "const s: Record<string, string> = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' };\nfunction Spinner({ size = 'md', className }: SpinnerProps) {\n  return <svg className={`animate-spin ${s[size]} ${className ?? ''}`} viewBox=\"0 0 24 24\" fill=\"none\" role=\"status\" aria-label=\"Loading\"><circle className=\"opacity-25\" cx=\"12\" cy=\"12\" r=\"10\" stroke=\"currentColor\" strokeWidth=\"4\" /><path className=\"opacity-75\" fill=\"currentColor\" d=\"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z\" /></svg>;\n}")

    files["src/components/ui/Avatar.tsx"] = _gen_simple("Avatar",
        "interface AvatarProps { src?: string; alt?: string; fallback?: string; size?: 'sm' | 'md' | 'lg'; }",
        "const s: Record<string, string> = { sm: 'h-8 w-8', md: 'h-10 w-10', lg: 'h-14 w-14' };\nfunction Avatar({ src, alt, fallback, size = 'md' }: AvatarProps) {\n  if (src) return <img src={src} alt={alt ?? ''} className={`rounded-full object-cover ${s[size]}`} />;\n  return <div className={`flex items-center justify-center rounded-full bg-gray-200 font-medium ${s[size]}`}>{fallback ?? '?'}</div>;\n}")

    files["src/components/ui/Divider.tsx"] = _gen_simple("Divider",
        "interface DividerProps { className?: string; label?: string; }",
        "function Divider({ className, label }: DividerProps) {\n  if (label) return <div className={`flex items-center gap-3 ${className ?? ''}`}><div className=\"flex-1 border-t\" /><span className=\"text-xs text-gray-500\">{label}</span><div className=\"flex-1 border-t\" /></div>;\n  return <hr className={className ?? ''} />;\n}")

    files["src/components/ui/EmptyState.tsx"] = _gen_simple("EmptyState",
        "interface EmptyStateProps { title: string; description?: string; icon?: React.ReactNode; action?: React.ReactNode; }",
        "function EmptyState({ title, description, icon, action }: EmptyStateProps) {\n  return <div className=\"flex flex-col items-center py-12 text-center\">{icon && <div className=\"mb-4 text-gray-400\">{icon}</div>}<h3 className=\"text-lg font-semibold\">{title}</h3>{description && <p className=\"mt-1 text-sm text-gray-500\">{description}</p>}{action && <div className=\"mt-4\">{action}</div>}</div>;\n}")

    files["src/components/ui/ErrorBoundary.tsx"] = (
        "import React from 'react';\n\n"
        "interface ErrorBoundaryProps { children: React.ReactNode; fallback?: React.ReactNode; }\n"
        "interface ErrorBoundaryState { hasError: boolean; error: Error | null; }\n\n"
        "class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {\n"
        "  constructor(props: ErrorBoundaryProps) { super(props); this.state = { hasError: false, error: null }; }\n"
        "  static getDerivedStateFromError(error: Error): ErrorBoundaryState { return { hasError: true, error }; }\n"
        "  render() {\n"
        "    if (this.state.hasError) return this.props.fallback ?? <div className=\"p-8 text-center\"><h2 className=\"text-red-600\">Something went wrong</h2><p className=\"text-sm text-gray-500\">{this.state.error?.message}</p></div>;\n"
        "    return this.props.children;\n"
        "  }\n"
        "}\n\n"
        "export type { ErrorBoundaryProps };\nexport default ErrorBoundary;\n"
    )

    # Barrel
    barrel = "\n".join(
        f"export {{ default as {n} }} from './{n}';\nexport type {{ {n}Props }} from './{n}';"
        for n in _COMPONENT_NAMES
    ) + "\n"
    files["src/components/ui/index.ts"] = barrel

    return files


async def run_component_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate shared UI components. temp=0, fixed seed."""
    start = time.monotonic()
    idea_spec = state.get("idea_spec", {})
    injected = state.get("injected_schemas", {})

    schema_ctx = ""
    for key in ("zod_schemas", "db_types"):
        if key in injected:
            schema_ctx += f"\n{key}:\n{str(injected[key])[:2000]}\n"

    user_prompt = (
        f"Project: {idea_spec.get('title', 'Untitled')}\n"
        f"Generate: Button, Input, Select, Textarea, Card, Modal, Toast, "
        f"Badge, Spinner, Avatar, Divider, EmptyState, ErrorBoundary\n"
        f"{schema_ctx}"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            agent_name=AGENT_NAME,
        )
        if files:
            logger.info("component_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("component_agent.llm_fallback", error=str(exc))

    files = _build_default_components(state)
    logger.info("component_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files
