/**
 * Chart rendering helpers for the Medicaid Provider Spending dashboard.
 * Uses Plotly.js for all chart rendering.
 */

/**
 * Render a monthly spending chart with total_paid on primary axis.
 */
function renderMonthlyChart(elementId, data) {
    var months = data.map(function(d) { return d.month; });
    var paid = data.map(function(d) { return d.total_paid; });

    var traces = [{
        x: months,
        y: paid,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Total Paid',
        line: { color: '#0d6efd', width: 2 },
        marker: { size: 4 },
        hovertemplate: '%{x}<br>$%{y:,.0f}<extra></extra>'
    }];

    var layout = {
        margin: { t: 20, b: 40, l: 80, r: 20 },
        xaxis: {
            title: '',
            tickangle: -45
        },
        yaxis: {
            title: 'Total Paid ($)',
            tickprefix: '$',
            tickformat: ',.0s'
        },
        hovermode: 'x unified'
    };

    Plotly.newPlot(elementId, traces, layout, { responsive: true });
}

/**
 * Render a simple line chart.
 */
function renderLineChart(elementId, xValues, yValues, name, color) {
    var traces = [{
        x: xValues,
        y: yValues,
        type: 'scatter',
        mode: 'lines+markers',
        name: name,
        line: { color: color || '#0d6efd', width: 2 },
        marker: { size: 4 },
        hovertemplate: '%{x}<br>%{y:,.0f}<extra></extra>'
    }];

    var layout = {
        margin: { t: 20, b: 40, l: 60, r: 20 },
        xaxis: { tickangle: -45 },
        yaxis: { tickformat: ',.0s' },
        hovermode: 'x unified'
    };

    Plotly.newPlot(elementId, traces, layout, { responsive: true });
}

/**
 * Render a horizontal bar chart.
 */
function renderBarChart(elementId, labels, values, color) {
    var traces = [{
        type: 'bar',
        x: values,
        y: labels,
        orientation: 'h',
        marker: { color: color || '#0d6efd' },
        text: values.map(function(v) { return '$' + v.toLocaleString(); }),
        textposition: 'auto'
    }];

    var layout = {
        margin: { l: 200, r: 20, t: 10, b: 40 },
        xaxis: { tickprefix: '$' },
        yaxis: { autorange: 'reversed' }
    };

    Plotly.newPlot(elementId, traces, layout, { responsive: true });
}

/**
 * Format a number as currency.
 */
function formatCurrency(value) {
    return '$' + Number(value).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}

/**
 * Format a large number with abbreviations (K, M, B).
 */
function formatNumber(value) {
    if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M';
    if (value >= 1e3) return (value / 1e3).toFixed(1) + 'K';
    return value.toLocaleString();
}
