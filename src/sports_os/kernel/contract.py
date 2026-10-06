from dataclasses import dataclass, field, asdict
from copy import deepcopy
from decimal import localcontext, ROUND_HALF_EVEN
from .data import KernelError, digest

@dataclass
class ModuleState:
    module_version: str
    schema_version: str
    payload: dict
    data_version: str = '1'
    status: str = 'DRAFT'
    approval_ref: str | None = None

    def to_dict(self):
        return asdict(self)

    @property
    def content_hash(self):
        return digest(self.to_dict())

@dataclass
class Project:
    manifest: dict
    states: dict[str, ModuleState] = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    # Workspace revision this copy was loaded at (Store); None = not loaded from a store. Never serialized.
    base_revision: int | None = field(default=None, compare=False, repr=False)

    @property
    def enabled(self):
        return sorted(k for k,v in self.manifest['modules'].items() if v)

    def to_dict(self, active_only=False):
        return dict(format_version='1.1',manifest=deepcopy(self.manifest),evidence=deepcopy(self.evidence),
                    modules={k:v.to_dict() for k,v in sorted(self.states.items()) if not active_only or k in self.enabled})

    @classmethod
    def from_dict(cls, data):
        if data.get('format_version')!='1.1':raise KernelError('不是模块格式1.1；请显式迁移')
        return cls(deepcopy(data['manifest']),{k:ModuleState(**v) for k,v in data['modules'].items()},deepcopy(data['evidence']))

class Module:
    """Third-party entry points expose a no-argument Module factory.

    Hooks are pure and deterministic. Only explicitly enabled modules are called.
    Schema and semantic migrations must be explicit, even when schema is unchanged.
    """
    module_id = ''
    # Presentation metadata for UIs (the desktop app shows these; nothing in the kernel depends on them).
    display_name = ''   # human name; UIs fall back to module_id
    category = 'Other'  # grouping label, e.g. Core / Ticketing / Rules / Finance / Product / Project
    description = ''    # one line: what data this module holds
    # When several installed modules provide a capability, this one is chosen automatically when a user
    # enables something that needs the capability (they can still switch to another provider).
    default_provider = False
    module_version = '1.1.0'
    schema_version = '1'
    dependencies = ()
    optional_dependencies = ()
    provides = ()
    requires_capabilities = ()
    optional_capabilities = ()

    def schema(self):
        raise NotImplementedError

    def validate(self, context, gate):
        pass

    def cross_validate(self, context, gate):
        pass

    def calculate(self, context):
        return None

    def diff(self, old, new):
        from .diff import changes
        return changes(old,new)

    def export(self, context):
        return None

    def release_requirements(self, context, gate):
        pass

    def prepare_revision(self, payload, data_version, approval_ref=None):
        """Pure module-owned synchronization of embedded lifecycle metadata."""
        return deepcopy(payload)

    def migrate(self, old_version, old_schema, payload):
        raise KernelError(f'{self.module_id}: 没有 {old_version}/{old_schema} 到 {self.module_version}/{self.schema_version} 的迁移')

class Context:
    def __init__(self,project,registry,for_release=False):
        self.project=deepcopy(project)
        self.registry=registry
        self.for_release=for_release
        self._results={}
        self._active=set()

    def enabled(self, module_id):
        return module_id in self.project.enabled

    def payload(self, module_id):
        if not self.enabled(module_id):raise KernelError(f'模块未启用：{module_id}')
        return deepcopy(self.project.states[module_id].payload)

    def calculate(self, module_id):
        if not self.enabled(module_id):raise KernelError(f'模块未启用：{module_id}')
        if module_id in self._active:raise KernelError('计算依赖循环')
        if module_id not in self._results:
            self._active.add(module_id)
            try:
                with localcontext() as decimal_context:
                    decimal_context.prec=80
                    decimal_context.rounding=ROUND_HALF_EVEN
                    self._results[module_id]=self.registry.get(module_id).calculate(self)
            finally:self._active.remove(module_id)
        return deepcopy(self._results[module_id])

    def provider(self, capability, required=True):
        matches=[m for m in self.project.enabled if capability in self.registry.get(m).provides]
        if len(matches)>1 or (not matches and required):
            raise KernelError(f'能力 {capability} 需要唯一启用的提供者，实际 {matches}')
        return self.calculate(matches[0]) if matches else None
