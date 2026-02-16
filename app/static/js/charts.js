/**
 * Chart rendering helpers for the Medicaid Provider Spending dashboard.
 * Uses Plotly.js for all chart rendering.
 *
 * [EN] Custom tick formatting uses abbreviations (K, M, B) instead of SI prefixes (k, M, G)
 *      and includes enough precision to avoid duplicate tick labels on the Y-axis.
 * [RU] Пользовательское форматирование меток использует сокращения (K, M, B) вместо SI-префиксов
 *      и включает достаточную точность для избежания дублирования меток на оси Y.
 * [PT] Formatacao personalizada de ticks usa abreviacoes (K, M, B) em vez de prefixos SI
 *      e inclui precisao suficiente para evitar rotulos duplicados no eixo Y.
 */

/**
 * Format a tick value with human-readable abbreviations (K, M, B).
 * Automatically adjusts decimal places to avoid duplicate labels.
 */
function formatTickValue(value) {
    var absVal = Math.abs(value);
    if (absVal >= 1e9) {
        var v = value / 1e9;
        return '$' + (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'B';
    }
    if (absVal >= 1e6) {
        var v = value / 1e6;
        return '$' + (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'M';
    }
    if (absVal >= 1e3) {
        var v = value / 1e3;
        return '$' + (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'K';
    }
    return '$' + value.toLocaleString();
}

/**
 * Format a plain number tick value with abbreviations (K, M, B) — no $ prefix.
 */
function formatPlainTickValue(value) {
    var absVal = Math.abs(value);
    if (absVal >= 1e9) {
        var v = value / 1e9;
        return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'B';
    }
    if (absVal >= 1e6) {
        var v = value / 1e6;
        return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'M';
    }
    if (absVal >= 1e3) {
        var v = value / 1e3;
        return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'k';
    }
    return value.toLocaleString();
}

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

    // [EN] Compute nice tick values to avoid duplicate labels
    // [RU] Вычисляем аккуратные значения меток для избежания дубликатов
    // [PT] Calcula valores de ticks adequados para evitar duplicatas
    var yMin = Math.min.apply(null, paid);
    var yMax = Math.max.apply(null, paid);
    var tickVals = computeNiceTicks(yMin, yMax, 6);

    var layout = {
        margin: { t: 20, b: 40, l: 80, r: 20 },
        xaxis: {
            title: '',
            tickangle: -45
        },
        yaxis: {
            title: 'Total Paid ($)',
            tickmode: 'array',
            tickvals: tickVals,
            ticktext: tickVals.map(formatTickValue)
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

    // [EN] Compute nice tick values with plain number formatting
    // [RU] Вычисляем аккуратные значения меток с простым числовым форматированием
    // [PT] Calcula valores de ticks com formatacao numerica simples
    var yMin = Math.min.apply(null, yValues);
    var yMax = Math.max.apply(null, yValues);
    var tickVals = computeNiceTicks(yMin, yMax, 6);

    var layout = {
        margin: { t: 20, b: 40, l: 70, r: 20 },
        xaxis: { tickangle: -45 },
        yaxis: {
            tickmode: 'array',
            tickvals: tickVals,
            ticktext: tickVals.map(formatPlainTickValue)
        },
        hovermode: 'x unified'
    };

    Plotly.newPlot(elementId, traces, layout, { responsive: true });
}

/**
 * Compute evenly spaced "nice" tick values for a given data range.
 * Returns an array of tick values that produce unique, readable labels.
 *
 * [EN] Finds the nearest "nice" step size (1, 2, 2.5, or 5 × 10^n) and generates
 *      evenly spaced ticks from a rounded minimum to a rounded maximum.
 * [RU] Находит ближайший «красивый» шаг (1, 2, 2.5 или 5 × 10^n) и генерирует
 *      равномерно распределённые метки от округлённого минимума до округлённого максимума.
 * [PT] Encontra o passo "bonito" mais proximo (1, 2, 2.5 ou 5 × 10^n) e gera
 *      ticks uniformemente espacados de um minimo arredondado a um maximo arredondado.
 */
function computeNiceTicks(dataMin, dataMax, targetCount) {
    if (dataMin === dataMax) return [dataMin];
    targetCount = targetCount || 6;

    var range = dataMax - dataMin;
    var roughStep = range / targetCount;

    // [EN] Find the magnitude of the rough step
    var mag = Math.pow(10, Math.floor(Math.log10(roughStep)));
    var normalized = roughStep / mag;

    // [EN] Choose a "nice" step: 1, 2, 2.5, 5, or 10
    var niceStep;
    if (normalized <= 1.5) niceStep = 1 * mag;
    else if (normalized <= 3) niceStep = 2 * mag;
    else if (normalized <= 7) niceStep = 5 * mag;
    else niceStep = 10 * mag;

    // [EN] Round min down and max up to nice step boundaries
    var niceMin = Math.floor(dataMin / niceStep) * niceStep;
    var niceMax = Math.ceil(dataMax / niceStep) * niceStep;

    var ticks = [];
    for (var v = niceMin; v <= niceMax + niceStep * 0.01; v += niceStep) {
        ticks.push(Math.round(v * 1e6) / 1e6); // avoid floating point noise
    }

    return ticks;
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
