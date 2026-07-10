import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

FIGSIZE_WIDE = (8, 4.5)
FIGSIZE_SQ = (6, 4.5)
COLORS_PURE = '#B0B0B0'
COLORS_RAG = '#6495C8'
COLORS_HYBRID = '#1F497D'

def fig_cost_comparison():
    models = ['Gemini 3.5\nFlash', 'DeepSeek\nV4 Flash', 'GPT-OSS\n20B', 'Qwen 3.5\n9B']
    pure = [0.80, 0.10, 0.02, 0.02]
    rag = [1.28, 0.09, 0.03, 0.03]
    hybrid = [0.28, 0.01, 0.01, 0.01]
    x = np.arange(len(models))
    w = 0.25
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    ax.bar(x - w, pure, w, label='Pure Prompting', color=COLORS_PURE)
    ax.bar(x, rag, w, label='RAG-Enhanced', color=COLORS_RAG)
    ax.bar(x + w, hybrid, w, label='LLM-Parameterized_Reference_Scoring', color=COLORS_HYBRID)
    ax.set_ylabel('Cost per 195-scenario run ($)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_yscale('log')
    ax.set_ylim(0.005, 5)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('paper/fig_cost_comparison.png', dpi=200, bbox_inches='tight')
    plt.close()
    print('fig_cost_comparison.png')

def fig_mae_criterion():
    criteria = ['Energy\nCost', 'Environmental', 'Comfort', 'Practicality']
    pure = [0.240, 0.260, 0.171, 0.206]
    rag = [0.147, 0.141, 0.134, 0.129]
    hybrid = [0.077, 0.098, 0.010, 0.020]
    x = np.arange(len(criteria))
    w = 0.25
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    ax.bar(x - w, pure, w, label='Pure Prompting', color=COLORS_PURE)
    ax.bar(x, rag, w, label='RAG-Enhanced', color=COLORS_RAG)
    ax.bar(x + w, hybrid, w, label='LLM-Parameterized_Reference_Scoring', color=COLORS_HYBRID)
    ax.set_ylabel('MAE (0--10 scale)')
    ax.set_xticks(x)
    ax.set_xticklabels(criteria)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('paper/fig_mae_criterion.png', dpi=200, bbox_inches='tight')
    plt.close()
    print('fig_mae_criterion.png')

def fig_tau_decision():
    decisions = ['HVAC', 'Appliance', 'Shower']
    pure = [0.031, -0.100, 0.381]
    rag = [0.107, 0.282, 0.669]
    hybrid = [0.936, 0.944, 0.817]
    x = np.arange(len(decisions))
    w = 0.25
    fig, ax = plt.subplots(figsize=FIGSIZE_SQ)
    ax.bar(x - w, pure, w, label='Pure Prompting', color=COLORS_PURE)
    ax.bar(x, rag, w, label='RAG-Enhanced', color=COLORS_RAG)
    ax.bar(x + w, hybrid, w, label='LLM-Parameterized_Reference_Scoring', color=COLORS_HYBRID)
    ax.axhline(y=0.0, color='gray', linestyle=':', linewidth=0.8, label='Random ($\\tau = 0$)')
    ax.set_ylabel("Kendall's $\\tau$")
    ax.set_xticks(x)
    ax.set_xticklabels(decisions)
    ax.set_ylim(-0.25, 1.05)
    ax.legend(frameon=False, fontsize=8, loc='lower left')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('paper/fig_tau_decision.png', dpi=200, bbox_inches='tight')
    plt.close()
    print('fig_tau_decision.png')

def fig_rag_ablation():
    configs = ['k=3\n(control)', 'k=1', 'k=5', 'No hidden\nparams', 'Alt\nembedding', 'No scores']
    gemini = [0.111, 0.346, 0.343, 0.200, 0.400, -0.079]
    deepseek = [0.002, 0.388, 0.168, 0.353, 0.410, -0.035]
    gptoss = [0.244, 0.289, 0.067, 0.366, 0.146, -0.044]
    qwen = [0.212, 0.422, 0.168, 0.200, 0.254, 0.048]
    x = np.arange(len(configs))
    w = 0.18
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    ax.bar(x - 2*w, gemini, w, label='Gemini', color='#4472C4')
    ax.bar(x - w, deepseek, w, label='DeepSeek', color='#ED7D31')
    ax.bar(x, gptoss, w, label='GPT-OSS', color='#70AD47')
    ax.bar(x + w, qwen, w, label='Qwen', color='#FFC000')
    ax.axhline(y=0.0, color='gray', linestyle=':', linewidth=0.8)
    ax.set_ylabel("Kendall's $\\tau$")
    ax.set_xticks(x)
    ax.set_xticklabels(configs)
    ax.legend(frameon=False, fontsize=8, ncol=4)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('paper/fig_rag_ablation.png', dpi=200, bbox_inches='tight')
    plt.close()
    print('fig_rag_ablation.png')

if __name__ == '__main__':
    fig_cost_comparison()
    fig_mae_criterion()
    fig_tau_decision()
    fig_rag_ablation()
    print('All charts generated.')
