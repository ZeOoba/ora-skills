"""ORA chart style for matplotlib. Import in any chart script:
    sys.path.insert(0, '<pkg>/lib'); from ora_chart_style import *
Gives palette constants, global rcParams, $K formatter, and a save() factory."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
NAVY='#1B2A4A'; GOLD='#C9A96E'; GREY='#8C94AB'; RED='#A62525'; GREEN='#1B7A4B'; LIGHT='#E8E3D6'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.edgecolor':'#B8B2A3','axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','axes.titlesize':11,'axes.titlecolor':NAVY,'text.color':'#222','axes.labelcolor':'#444','xtick.color':'#444','ytick.color':'#444'})
k=lambda v:f"${v/1000:,.0f}K"
kfmt=FuncFormatter(lambda v,p:f"${v/1000:,.0f}K")
mfmt=FuncFormatter(lambda v,p:f"${v/1e6:.1f}M")
def make_save(out_dir):
    def save(fig,name):
        fig.savefig(out_dir+name,dpi=200,bbox_inches='tight',facecolor='white'); plt.close(fig)
    return save
