# Examples

Each example is a short recipe (a text file) and the figure PyFigures builds from it. Click one to see its recipe and how to run it. Every feature shown can also be used from the PyFigures window or the MCP server.

<style>.pyf-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin:1em 0}.pyf-card{display:flex;flex-direction:column;border:1px solid #e1e4e5;border-radius:4px;padding:10px;color:inherit;text-decoration:none}.pyf-card:hover{border-color:#2980b9}.pyf-card img{width:100%;height:150px;object-fit:contain;background:#f8f8f8;margin-bottom:8px}.pyf-card b{color:#2980b9;margin-bottom:4px}.pyf-card span{font-size:90%}</style>
<div class="pyf-gallery">
<a class="pyf-card" href="basic.html"><img src="basic/figure.png" alt="Micrographs with scale bars and letters"><b>Micrographs with scale bars and letters</b><span>Two crops of the same image side by side, lettered A and B, each with a scale bar, sized for a Nature single column.</span></a>
<a class="pyf-card" href="channels.html"><img src="channels/figure.png" alt="Channel split and merge"><b>Channel split and merge</b><span>Two channels shown separately in their own colours, then merged, with names on the panels and one scale bar.</span></a>
<a class="pyf-card" href="annotations.html"><img src="annotations/figure.png" alt="Arrows, regions and text"><b>Arrows, regions and text</b><span>Arrows whose tips stay exactly on the cells they point at, outlined regions, and text in the corners.</span></a>
<a class="pyf-card" href="zoom.html"><img src="zoom/figure.png" alt="Zoom callout"><b>Zoom callout</b><span>A region of a large histology image magnified in a corner, with the box and the leader lines drawn automatically.</span></a>
<a class="pyf-card" href="timelapse.html"><img src="timelapse/figure.png" alt="Time-lapse montage with time stamps"><b>Time-lapse montage with time stamps</b><span>Five frames of a movie in a row, each stamped with its time.</span></a>
<a class="pyf-card" href="plot.html"><img src="plot/figure.png" alt="Image and data plot with statistics"><b>Image and data plot with statistics</b><span>A micrograph next to a box plot made from a CSV file. The statistical test is chosen automatically (here ANOVA with Tukey's post-hoc test), the significance brackets are drawn, and every p-value is saved with the figure.</span></a>
<a class="pyf-card" href="latex.html"><img src="latex/figure.png" alt="LaTeX: maths in labels and equation panels"><b>LaTeX: maths in labels and equation panels</b><span>Labels can contain LaTeX maths between dollars, and an equation can be a panel of its own (here a row of its own, so it keeps a modest height). Both are vector in every export. Here the equation uses Matplotlib's built-in maths; with engine: latex it is compiled by LaTeX itself (any environment, any package).</span></a>
<a class="pyf-card" href="poster.html"><img src="poster/poster.png" alt="A poster with a figure on it"><b>A poster with a figure on it</b><span>A poster page with a title, a scientific figure dropped in from its .pyf file (kept vector in PDF/SVG exports, with editable text) and a photo.</span></a>
</div>

---

Sample images from [scikit-image](https://scikit-image.org/docs/stable/api/skimage.data.html): `human_mitosis` (nuclei, Moffat et al., Cell 2006), `cells3d` (membrane and nuclei, Allen Institute for Cell Science), `protein_transport` (time-lapse, Boisvert et al.), `skin` (H&E-stained skin). The CSV data are simulated.
