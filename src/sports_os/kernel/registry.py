from importlib.metadata import entry_points
from .data import KernelError
from .contract import Module

class Registry:
    def __init__(self):
        self._modules={}
        self.load_errors={}  # entry-point name -> why the plugin could not be loaded

    def problems(self):
        return [dict(module_id=k,error=v) for k,v in sorted(self.load_errors.items())]

    def register(self, module, replace=False):
        """Add a module. ``replace=True`` swaps an implementation explicitly; existing working state is not
        reinterpreted: the gate BLOCKs (K003) until states match the new module/schema version via migrate."""
        if not isinstance(module,Module) or not module.module_id:
            raise KernelError('插件必须实现Module协议并提供module_id')
        if module.module_id in self._modules and not replace:
            raise KernelError('重复模块ID：'+module.module_id)
        self._modules[module.module_id]=module

    @classmethod
    def discover(cls):
        """Load every installed plugin. A plugin that fails to import or construct is recorded in
        ``load_errors`` and skipped, so one broken package cannot take down the others. Projects that
        enable it still BLOCK (the module is unavailable). Duplicate module IDs remain a hard error:
        silently choosing one implementation would be worse than refusing."""
        registry=cls()
        for ep in sorted(entry_points(group='sports_os.modules'),key=lambda e:e.name):
            try:module=ep.load()()
            except Exception as e:
                registry.load_errors[ep.name]=f'{type(e).__name__}: {e}';continue
            if not isinstance(module,Module) or not module.module_id:
                registry.load_errors[ep.name]='入口没有返回带module_id的Module实例';continue
            registry.register(module)
        return registry

    def get(self, module_id):
        try:return self._modules[module_id]
        except KeyError:
            if module_id in self.load_errors:raise KernelError(f'模块无法加载：{module_id}（{self.load_errors[module_id]}）') from None
            raise KernelError('未安装模块：'+module_id) from None

    def list(self):
        return [dict(module_id=m.module_id,display_name=m.display_name or m.module_id,category=m.category or 'Other',description=m.description,
                     module_version=m.module_version,schema_version=m.schema_version,
                     dependencies=list(m.dependencies),optional_dependencies=list(m.optional_dependencies),
                     provides=list(m.provides),requires_capabilities=list(m.requires_capabilities),
                     optional_capabilities=list(m.optional_capabilities))
                for _,m in sorted(self._modules.items())]

    def with_dependencies(self, selected):
        """Return (modules, added) where modules = selected plus everything they need to run, and added maps
        each automatically added module to the module that needed it. Required capabilities already
        provided by a selected module are left alone; otherwise the installed provider is used, preferring
        one marked ``default_provider`` when several exist."""
        chosen=list(dict.fromkeys(selected));added={}
        queue=list(chosen)
        while queue:
            key=queue.pop(0);module=self.get(key)
            needs=[(dep,None) for dep in module.dependencies]+[(None,cap) for cap in module.requires_capabilities]
            for dep,cap in needs:
                if cap is not None:
                    if any(cap in self.get(k).provides for k in chosen):continue
                    providers=sorted(m.module_id for m in self._modules.values() if cap in m.provides)
                    preferred=[k for k in providers if self.get(k).default_provider]
                    if len(preferred)!=1 and len(providers)!=1:
                        raise KernelError(f'{key} 需要能力 {cap}，可选提供者 {providers}；请先启用其中一个')
                    dep=(preferred or providers)[0]
                if dep not in chosen:
                    chosen.append(dep);added[dep]=key;queue.append(dep)
        return chosen,added

    def order(self, enabled):
        graph=self.dependency_graph(enabled)
        result=[];visiting=set();done=set()
        def visit(key):
            if key in visiting:raise KernelError('模块依赖循环：'+key)
            if key in done:return
            visiting.add(key)
            for dep in sorted(graph[key]):visit(dep)
            visiting.remove(key);done.add(key);result.append(key)
        for key in sorted(graph):visit(key)
        return result

    def dependency_graph(self, enabled):
        """module_id -> set of enabled modules it depends on (modules and capability providers)."""
        enabled=set(enabled);graph={}
        for key in sorted(enabled):
            m=self.get(key);missing=set(m.dependencies)-enabled
            if missing:raise KernelError(f'{key} 缺依赖 {sorted(missing)}')
            deps=set(m.dependencies)|(set(m.optional_dependencies)&enabled)
            for cap in m.requires_capabilities:
                providers=[k for k in enabled if cap in self.get(k).provides]
                if len(providers)!=1:raise KernelError(f'{key}: 能力 {cap} 提供者必须唯一：{providers}')
                deps.add(providers[0])
            for cap in m.optional_capabilities:
                deps.update(k for k in enabled if cap in self.get(k).provides)
            graph[key]=deps
        caps={}
        for key in sorted(enabled):
            for cap in self.get(key).provides:
                if cap in caps:raise KernelError(f'能力冲突 {cap}: {caps[cap]}, {key}')
                caps[cap]=key
        return graph
