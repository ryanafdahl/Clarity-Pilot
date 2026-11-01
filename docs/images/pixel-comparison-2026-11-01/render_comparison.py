"""Render a Pixel comparison from its sanitized summary JSON.

Install: python -m pip install matplotlib
Usage: python render_comparison.py comparison.json --output-prefix pixel-comparison
Outputs PNG, SVG, and a concise copyable text comparison.

The summary must contain measurements from actual tests. This renderer never
recomputes or invents test data; make_chart.py validates the private raw captures.
"""
from pathlib import Path
import argparse
import json
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def render_comparison(summary, output_prefix):
    output = Path(output_prefix)
    output.parent.mkdir(parents=True, exist_ok=True)
    phones = summary['phones']
    if len(phones) != 2:
        raise ValueError('This chart compares exactly two phones')
    for record in phones:
        for key in ('average_ms', 'p95_ms', 'worst_ms'):
            if not math.isfinite(record[key]) or record[key] <= 0:
                raise ValueError(f'Invalid measured metric: {key}')
        if not 0 < record['measured_frames'] <= record['requested_frames']:
            raise ValueError('Invalid completed/requested frame counts')
        if not 0 <= record['completed_runs'] <= record['requested_runs']:
            raise ValueError('Invalid completed/requested run counts')
    colors = ['#B64B1A','#126C94']
    ink, muted, background = '#172A3A','#4F6271','#F5F7F8'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'svg.fonttype':'path'})
    fig = plt.figure(figsize=(12.8,8),dpi=100,facecolor=background)
    fig.text(.06,.95,'Pixel 10 vs Pixel 11',ha='left',va='top',fontsize=28,fontweight='bold',color=ink)
    fig.text(.06,.888,'JetLink phone processing time',ha='left',va='top',fontsize=17,color=ink)
    fig.text(.06,.848,f"Same app: {summary['app']}  |  Same model: {summary['model']}",
             ha='left',va='top',fontsize=11.5,color=muted)
    for i, (record,color) in enumerate(zip(phones,colors)):
        x = .06 + i*.46
        fig.add_artist(FancyBboxPatch((x,.66),.42,.143,boxstyle='round,pad=0.012,rounding_size=0.012',
                                     transform=fig.transFigure,facecolor='white',edgecolor='#DCE3E8',linewidth=1))
        fig.text(x+.012,.782,record['phone']+' · '+record['soc'].replace('_',' '),
                 ha='left',va='top',fontsize=14,fontweight='bold',color=color)
        run_word = 'run' if record['requested_runs']==1 else 'runs'
        fig.text(x+.012,.747,f"{record['measured_frames']:,} / {record['requested_frames']:,} measured frames · {record['completed_runs']}/{record['requested_runs']} {run_word} complete",
                 ha='left',va='top',fontsize=10.5,color=ink)
        if record['completed_runs'] < record['requested_runs']:
            timing_stop = any('timing limit' in s for r in record['runs'] for s in r['stop_reasons'])
            state = 'PARTIAL / FAILED · timing guard stopped test' if timing_stop else 'PARTIAL / FAILED · test stopped early'
        elif record['phone_guard_pass']:
            state = 'Completed · phone timing passed'
        else:
            state = 'Completed · over the phone timing budget'
        fig.text(x+.012,.715,state,ha='left',va='top',fontsize=10.5,fontweight='bold',color=color)
        over = record['measured_frames_over_50ms']
        fig.text(x+.012,.686,f"Over 50 ms: {over:,} measured frames ({100*over/record['measured_frames']:.1f}%)",
                 ha='left',va='top',fontsize=10.5,color=ink)
    # Typical timing controls the bar scale. Keep the actual maximum visible
    # below as a number, so a rare large stall cannot flatten these comparisons.
    ax = fig.add_axes([.18,.365,.73,.25],facecolor=background)
    metrics = [('average_ms','Average'),('p95_ms','p95')]
    centers = [1.2,.2]
    maximum = max(record[key] for record in phones for key,_ in metrics)
    xmax = max(70,math.ceil(maximum*1.24/10)*10)
    ax.set_xlim(0,xmax)
    ax.set_ylim(-.25,1.65)
    ax.set_yticks(centers,[label for _,label in metrics],fontsize=14,color=ink)
    ax.tick_params(axis='y',length=0,pad=18)
    ax.tick_params(axis='x',colors=muted,labelsize=10.5,length=0,pad=10)
    ax.xaxis.grid(True,color='#DCE3E8',linewidth=.8,zorder=0)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.axvline(50,color='#667887',linewidth=1.5,linestyle=(0,(4,3)),zorder=2)
    ax.text(50,1.67,'50 ms budget',ha='center',va='bottom',color=muted,fontsize=11,
            bbox={'facecolor':background,'edgecolor':'none','pad':3})
    for j,(record,color) in enumerate(zip(phones,colors)):
        offset = .17 if j==0 else -.17
        for center,(key,_) in zip(centers,metrics):
            value = record[key]
            ax.barh(center+offset,value,height=.27,color=color,zorder=3)
            ax.text(value+xmax*.012,center+offset,f'{value:.2f} ms',ha='left',va='center',
                    fontsize=11.5,fontweight='bold',color=ink)
    ax.set_xlabel('Milliseconds per measured frame · lower is faster',color=muted,labelpad=15,fontsize=11.5)
    fig.text(.06,.255,'Slowest measured frame',ha='left',va='top',fontsize=13,fontweight='bold',color=ink)
    fig.text(.40,.255,f"Pixel 10: {phones[0]['worst_ms']:.2f} ms",ha='left',va='top',
             fontsize=14,fontweight='bold',color=colors[0])
    fig.text(.70,.255,f"Pixel 11: {phones[1]['worst_ms']:.2f} ms",ha='left',va='top',
             fontsize=14,fontweight='bold',color=colors[1])
    fig.text(.06,.215,(f"All outliers retained · measured frames at or above 100 ms: "
             f"Pixel 10 {phones[0]['measured_frames_at_or_over_100ms']:,}; "
             f"Pixel 11 {phones[1]['measured_frames_at_or_over_100ms']:,}."),
             ha='left',va='top',fontsize=10.5,color=muted)
    partial = any(p['completed_runs']<p['requested_runs'] for p in phones)
    run_count = 'One run' if phones[0]['requested_runs']==1 else f"{phones[0]['requested_runs']} runs"
    line1 = 'Partial tests: stopped runs include only the frames completed before the stop.' if partial else (
        f"{run_count} per phone · {phones[0]['requested_frames']:,} measured frames each · Pixel 10: {phones[0]['total_elapsed_s']/60:.1f} min; "
        f"Pixel 11: {phones[1]['total_elapsed_s']/60:.1f} min total.")
    fig.text(.06,.145,line1,ha='left',va='top',fontsize=10.5,color=ink)
    warm_count = (f"{phones[0]['warmup_frames']} warmup frames per phone excluded" if phones[0]['warmup_frames']==phones[1]['warmup_frames'] else
                  f"Warmup excluded: Pixel 10 {phones[0]['warmup_frames']}; Pixel 11 {phones[1]['warmup_frames']}")
    warm = (f"{warm_count}. Over 50 ms: Pixel 10 {phones[0]['warmup_frames_over_50ms']} (max {phones[0]['warmup_worst_ms']:.2f} ms); "
            f"Pixel 11 {phones[1]['warmup_frames_over_50ms']} (max {phones[1]['warmup_worst_ms']:.2f} ms).")
    fig.text(.06,.110,warm+'  p95 = 95th percentile.',
             ha='left',va='top',fontsize=10,color=muted)
    fig.text(.06,.075,'Pixel 10 overruns recorded without stopping. Phone time excludes transport. Synthetic PC ADB; direct comma USB untested.',
             ha='left',va='top',fontsize=10,color=muted)
    fig.text(.06,.042,'November 1, 2026 · Earlier Pixel 11 275 ms stall remains unresolved; these runs do not establish driving readiness.',
             ha='left',va='top',fontsize=9.5,color=muted)
    fig.savefig(output.with_suffix('.png'),dpi=100,facecolor=background)
    fig.savefig(output.with_suffix('.svg'),facecolor=background)
    svg = output.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8', newline='\n')
    plt.close(fig)
    output.with_suffix('.txt').write_text(comparison_text(summary),encoding='utf-8')


def comparison_text(summary):
    lines = ['Pixel 10 vs Pixel 11 — JetLink phone processing',
             f"App: {summary['app']} | Model: {summary['model']}",
             f"Selected run IDs: {', '.join(map(str,summary['selected_run_ids']))} for each phone. Lower times are better.", '']
    for record in summary['phones']:
        n = record['measured_frames']
        over = record['measured_frames_over_50ms']
        status = 'phone timing passed' if record['phone_guard_pass'] else 'phone timing budget exceeded'
        lines.append(f"{record['phone']} ({record['soc'].replace('_',' ')}): {n:,}/{record['requested_frames']:,} measured frames; {record['completed_runs']}/{record['requested_runs']} runs completed; {status}.")
        lines.append(f"Average {record['average_ms']:.2f} ms | p95 {record['p95_ms']:.2f} ms | worst {record['worst_ms']:.2f} ms | over 50 ms: {over:,}/{n:,} ({100*over/n:.1f}%) | elapsed {record['total_elapsed_s']/60:.2f} min.")
        if all(k in record for k in ('battery_c_start','battery_c_end','battery_c_peak')):
            lines.append(f"Battery temperature: {record['battery_c_start']:.1f} → {record['battery_c_end']:.1f} °C; peak {record['battery_c_peak']:.1f} °C.")
        lines.append(f"Warmup excluded: {record['warmup_frames']} frames; {record['warmup_frames_over_50ms']} over 50 ms; maximum {record['warmup_worst_ms']:.2f} ms.")
        lines.append('')
    lines.extend(['Pixel 10 timing overruns were recorded without stopping; all measured slow frames are included.',
                  'Synthetic desk tests through PC ADB. These are phone-processing times, not total vehicle latency; direct comma USB was not tested.',
                  'Earlier Pixel 11 275 ms stall remains unresolved. This comparison does not establish driving readiness.'])
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path, help='Sanitized comparison JSON')
    parser.add_argument('--output-prefix', type=Path,
                        help='Output basename without extension; defaults beside the JSON')
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding='utf-8-sig'))
    output = args.output_prefix or args.summary.with_suffix('')
    render_comparison(summary, output)
    print(f'Wrote {output.with_suffix(".png")}, {output.with_suffix(".svg")}, and {output.with_suffix(".txt")}')


if __name__ == '__main__':
    main()
