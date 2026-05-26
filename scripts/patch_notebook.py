import json

with open("notebooks/02_treinamento.ipynb") as f:
    nb = json.load(f)

# Add IPython display import to the imports cell
for cell in nb["cells"]:
    if cell["cell_type"] != "code": continue
    src = "".join(cell["source"])
    if "import seaborn as sns" in src:
        new = src.replace(
            "import seaborn as sns",
            "import seaborn as sns\nfrom IPython.display import display as ipy_display"
        )
        cell["source"] = [new]
        break

# Replace plt.show() with ipy_display(plt.gcf()) + plt.close
replaced = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code": continue
    src = "".join(cell["source"])
    if "plt.show()" in src:
        new = src.replace("plt.show()", 'ipy_display(plt.gcf()); plt.close("all")')
        cell["source"] = [new]
        replaced += 1

with open("notebooks/02_treinamento.ipynb", "w") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Patched: {replaced} plot cells updated to use ipy_display()")