import json
import tomllib
from pathlib import Path
from ..kernel.data import KernelError

PROFILES={
 'non-ticketed-event':('core.schedule','core.venue','project.tasks'),
 'ticketed-indoor-event':('core.schedule','core.venue','ticketing.pricing','ticketing.seating','ticketing.inventory','demand.multiplicative','finance.revenue'),
 'multi-session-tournament':('core.schedule','core.venue','ticketing.pricing','ticketing.seating','ticketing.inventory','demand.multiplicative','finance.revenue','product.pass'),
}

# Plain-language starting points for the new-project screen. Each lists only the modules the user would
# pick; anything those modules need (dependencies, capability providers) is added automatically.
TEMPLATES=(
 dict(id='non-ticketed-event',label='免费 / 不售票活动',
      description='赛程、场馆和工作任务。适合社区赛、训练营、公开课等不卖票的活动。',
      modules=PROFILES['non-ticketed-event']),
 dict(id='ticketed-indoor-event',label='售票赛事',
      description='在赛程和场馆之外，管理票价、座席、库存，并预估票房收入。',
      modules=PROFILES['ticketed-indoor-event']),
 dict(id='multi-session-tournament',label='多场次锦标赛（含通票）',
      description='多天、多场次的售票赛事，另外支持通票 / 套票产品。',
      modules=PROFILES['multi-session-tournament']),
 dict(id='custom',label='自定义',description='自己选择需要的功能模块；所需的依赖模块会自动加上。',modules=()),
)


def parse_manifest(path):
    with Path(path).open('rb') as f:return tomllib.load(f)

def render_manifest(manifest):
    lines=['[project]']
    for key,value in manifest['project'].items():
        # TOML has no null; empty approval is still invalid when marked approved.
        value='' if value is None else value
        lines.append(f'{key} = {json.dumps(value,ensure_ascii=False)}')
    lines+=['','[modules]']
    for key,value in sorted(manifest['modules'].items()):lines.append(f'{json.dumps(key)} = {str(value).lower()}')
    return '\n'.join(lines)+'\n'

def safe_path(workspace,path):
    root=Path(workspace).resolve()
    if root==Path('/Volumes') or Path('/Volumes') in root.parents:raise KernelError('不得读写/Volumes；使用独立本地工作目录')
    target=Path(path);target=(target if target.is_absolute() else root/target).resolve()
    if target!=root and root not in target.parents:raise KernelError('路径超出工作目录（含符号链接）')
    return target
