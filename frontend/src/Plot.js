// Bind react-plotly.js to the lightweight prebuilt bundle so Vite doesn't try to
// compile plotly.js from source.
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

export default createPlotlyComponent(Plotly);
