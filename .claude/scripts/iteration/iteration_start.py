"""iteration_start.py - Record baseline state before implementation."""
import json
import os
import glob
import subprocess
import sys
from datetime import datetime

# Force UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run_git(project_dir, args):
    try:
        return subprocess.check_output(
            ['git', '-C', project_dir] + args,
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return ''


def _storage_dirs(base_dir):
    """Resolve iteration/report storage paths.
    Real project (has CLAUDE.md or source dirs) → <project>/docs/iterations/
    Claude home fallback → ~/.claude/iterations/ and ~/.claude/reports/
    """
    claude_home = os.path.join(os.path.expanduser('~'), '.claude')
    if os.path.normpath(base_dir) == os.path.normpath(claude_home):
        return (os.path.join(claude_home, 'iterations'),
                os.path.join(claude_home, 'reports'))
    # Any project directory → use docs/iterations/
    return (os.path.join(base_dir, 'docs', 'iterations'),
            os.path.join(base_dir, 'docs', 'iterations'))


def main():
    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    iteration_dir, reports_dir = _storage_dirs(project_dir)
    plans_dir = os.path.join(os.path.expanduser('~'), '.claude', 'plans')
    os.makedirs(iteration_dir, exist_ok=True)

    # Remove old start records (keep only current baseline)
    for old in glob.glob(os.path.join(iteration_dir, '*-start.json')):
        try:
            os.remove(old)
        except OSError:
            pass

    now = datetime.now()
    iter_id = now.strftime('%Y-%m-%d-%H%M%S')
    start_file = os.path.join(iteration_dir, f'{iter_id}-start.json')

    # Find active plan (most recently modified plan file)
    active_plan = None
    if os.path.isdir(plans_dir):
        plan_files = sorted(
            [f for f in glob.glob(os.path.join(plans_dir, '*.md'))],
            key=os.path.getmtime, reverse=True
        )
        if plan_files:
            plan_name = os.path.basename(plan_files[0]).replace('.md', '')
            with open(plan_files[0], 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract task list from plan
            lines = content.split('\n')
            in_steps = False
            plan_tasks = []
            step_keywords = ['实施步骤', 'implementation steps', '## steps', '### step']

            for line in lines:
                s = line.strip()
                if any(kw in s.lower() for kw in step_keywords):
                    in_steps = True
                    continue
                if in_steps and s.startswith('##') and 'step' not in s.lower():
                    break
                if in_steps and (s.startswith('- [') or s.startswith('- **Step') or
                                 (s[:1].isdigit() and '. ' in s[:5])):
                    done = s.startswith('- [x]') or s.startswith('- [X]') or '✅' in s
                    plan_tasks.append({
                        'text': s.lstrip('- ').lstrip('0123456789. '),
                        'done': done
                    })

            active_plan = {
                'name': plan_name,
                'tasks': plan_tasks,
                'tasks_total': len(plan_tasks),
                'tasks_done': sum(1 for t in plan_tasks if t['done'])
            }

    # Git status
    git_info = {'branch': 'unknown', 'last_commit': 'N/A',
                'modified_files': [], 'staged_files': [], 'untracked_files': []}

    if os.path.isdir(os.path.join(project_dir, '.git')):
        try:
            git_info['branch'] = run_git(project_dir, ['rev-parse', '--abbrev-ref', 'HEAD'])
            git_info['last_commit'] = run_git(project_dir, ['log', '-1', '--format=%h %s (%an, %ar)'])

            has_diff = subprocess.call(
                ['git', '-C', project_dir, 'diff', '--quiet'],
                stderr=subprocess.DEVNULL
            )
            if has_diff:
                mod = run_git(project_dir, ['diff', '--name-only']).split('\n')
                git_info['modified_files'] = [f for f in mod if f]

            has_staged = subprocess.call(
                ['git', '-C', project_dir, 'diff', '--cached', '--quiet'],
                stderr=subprocess.DEVNULL
            )
            if has_staged:
                staged = run_git(project_dir, ['diff', '--cached', '--name-only']).split('\n')
                git_info['staged_files'] = [f for f in staged if f]

            untracked = run_git(project_dir, ['ls-files', '--others', '--exclude-standard']).split('\n')
            git_info['untracked_files'] = [f for f in untracked if f]
        except Exception:
            pass

    # Build iteration record
    record = {
        'iteration_id': iter_id,
        'timestamp': now.isoformat(),
        'project_dir': project_dir,
        'plan': active_plan,
        'git': git_info,
    }

    with open(start_file, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    # Build summary message
    plan_summary = ''
    if active_plan:
        done = active_plan['tasks_done']
        total = active_plan['tasks_total']
        plan_summary = f'\n  方案: {active_plan["name"][:60]}\n  任务进度: {done}/{total}'

    msg = (
        f'📋 迭代记录已创建: {iter_id}{plan_summary}'
        f'\n  分支: {git_info["branch"]} | 修改: {len(git_info["modified_files"])}文件'
    )

    # Output as systemMessage (read by Claude Code hook system)
    print(json.dumps({'systemMessage': msg}, ensure_ascii=False))


if __name__ == '__main__':
    main()
