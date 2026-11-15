import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/models.dart';
import 'theme.dart';

class TrendCard extends StatefulWidget {
  final List<DayStats> days;
  final Model model;
  final bool bundles;
  const TrendCard({super.key, required this.days, required this.model, required this.bundles});

  @override
  State<TrendCard> createState() => _TrendCardState();
}

class _TrendCardState extends State<TrendCard> {
  int range = 30; // days; 0 = all

  @override
  Widget build(BuildContext context) {
    final pts = <(DateTime, Stats)>[];
    for (final d in widget.days) {
      final s = d.get(widget.model, widget.bundles);
      if (s != null) pts.add((d.date, s));
    }
    final cutoff = range == 0 ? null : DateTime.now().subtract(Duration(days: range));
    final shown = cutoff == null ? pts : pts.where((p) => p.$1.isAfter(cutoff)).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Expanded(
              child: Text('Price trend', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            ),
            for (final r in const [7, 30, 90, 0])
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: _RangeChip(
                  label: r == 0 ? 'All' : '${r}D',
                  selected: range == r,
                  onTap: () => setState(() => range = r),
                ),
              ),
          ]),
          const SizedBox(height: 6),
          const Wrap(spacing: 14, children: [
            _Legend(Palette.down, 'Lowest'),
            _Legend(Palette.cyan, 'Median'),
            _Legend(Palette.up, 'Highest'),
          ]),
          const SizedBox(height: 14),
          SizedBox(
            height: 210,
            child: shown.length < 2
                ? _NotEnough(shown.isEmpty ? null : shown.first.$2)
                : _chart(shown),
          ),
          if (shown.length >= 2) ...[
            const SizedBox(height: 10),
            _Summary(shown),
          ],
        ]),
      ),
    );
  }

  Widget _chart(List<(DateTime, Stats)> pts) {
    final t0 = pts.first.$1;
    double x(DateTime d) => d.difference(t0).inHours / 24.0;
    final minY = pts.map((p) => p.$2.min).reduce(min).toDouble();
    final maxY = pts.map((p) => p.$2.max).reduce(max).toDouble();
    final pad = max(500.0, (maxY - minY) * .12);
    final lo = ((minY - pad) / 1000).floor() * 1000.0;
    final hi = ((maxY + pad) / 1000).ceil() * 1000.0;
    final spanDays = x(pts.last.$1);
    final fmt = DateFormat(spanDays > 120 ? 'MMM' : 'd MMM');

    LineChartBarData line(int Function(Stats) f, Color c, {double w = 2.6, bool area = false}) => LineChartBarData(
          spots: [for (final p in pts) FlSpot(x(p.$1), f(p.$2).toDouble())],
          isCurved: true,
          curveSmoothness: .25,
          preventCurveOverShooting: true,
          color: c,
          barWidth: w,
          dotData: FlDotData(show: pts.length <= 14, getDotPainter: (s, a, b, i) => FlDotCirclePainter(radius: 2.6, color: c, strokeWidth: 0)),
          belowBarData: area
              ? BarAreaData(
                  show: true,
                  gradient: LinearGradient(
                    colors: [c.withValues(alpha: .22), c.withValues(alpha: 0)],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
                )
              : BarAreaData(show: false),
        );

    return LineChart(
      LineChartData(
        minY: lo,
        maxY: hi,
        minX: 0,
        maxX: max(1, spanDays),
        gridData: FlGridData(
          drawVerticalLine: false,
          horizontalInterval: _niceStep(hi - lo),
          getDrawingHorizontalLine: (_) => const FlLine(color: Palette.line, strokeWidth: 1, dashArray: [4, 4]),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 40,
              interval: _niceStep(hi - lo),
              getTitlesWidget: (v, m) => Text(compact(v.round()),
                  style: const TextStyle(color: Palette.muted, fontSize: 10.5, fontWeight: FontWeight.w600)),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 24,
              interval: max(1, (spanDays / 4).ceilToDouble()),
              getTitlesWidget: (v, m) => Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(fmt.format(t0.add(Duration(hours: (v * 24).round()))),
                    style: const TextStyle(color: Palette.muted, fontSize: 10.5)),
              ),
            ),
          ),
        ),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipColor: (_) => Palette.surface2,
            tooltipBorderRadius: BorderRadius.circular(12),
            fitInsideHorizontally: true,
            fitInsideVertically: true,
            getTooltipItems: (spots) => [
              for (var i = 0; i < spots.length; i++)
                LineTooltipItem(
                  (i == 0 ? '${DateFormat('EEE d MMM').format(t0.add(Duration(hours: (spots[i].x * 24).round())))}\n' : '') +
                      '${['Low', 'Median', 'High'][spots[i].barIndex]}  ${num0(spots[i].y.round())}',
                  TextStyle(color: spots[i].bar.color, fontWeight: FontWeight.w700, fontSize: 12),
                ),
            ],
          ),
        ),
        lineBarsData: [
          line((s) => s.min, Palette.down, area: true),
          line((s) => s.median, Palette.cyan, w: 2),
          line((s) => s.max, Palette.up, w: 1.6),
        ],
      ),
      duration: const Duration(milliseconds: 300),
    );
  }

  double _niceStep(double span) {
    for (final s in [500, 1000, 2000, 2500, 5000, 10000, 20000]) {
      if (span / s <= 5) return s.toDouble();
    }
    return 50000;
  }
}

class _Summary extends StatelessWidget {
  final List<(DateTime, Stats)> pts;
  const _Summary(this.pts);

  @override
  Widget build(BuildContext context) {
    final lows = pts.map((p) => p.$2.min).toList();
    final first = pts.first.$2.min, last = pts.last.$2.min;
    final allTimeLow = lows.reduce(min);
    final lowDay = pts.firstWhere((p) => p.$2.min == allTimeLow).$1;
    final diff = last - first;
    return Row(children: [
      Expanded(
        child: _Mini('Lowest in range', num0(allTimeLow), DateFormat('d MMM').format(lowDay)),
      ),
      Expanded(
        child: _Mini('Lowest price moved', '${diff > 0 ? '+' : diff < 0 ? '−' : ''}${num0(diff.abs())}',
            'since ${DateFormat('d MMM').format(pts.first.$1)}',
            color: diff > 0 ? Palette.up : diff < 0 ? Palette.down : null),
      ),
    ]);
  }
}

class _Mini extends StatelessWidget {
  final String label, value, sub;
  final Color? color;
  const _Mini(this.label, this.value, this.sub, {this.color});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(color: Palette.muted, fontSize: 11.5, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: color)),
        Text(sub, style: const TextStyle(color: Palette.muted, fontSize: 11)),
      ]);
}

class _NotEnough extends StatelessWidget {
  final Stats? today;
  const _NotEnough(this.today);

  @override
  Widget build(BuildContext context) => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.show_chart_rounded, color: Palette.muted, size: 36),
          const SizedBox(height: 8),
          const Text('The curve builds up one point per day',
              style: TextStyle(fontWeight: FontWeight.w700), textAlign: TextAlign.center),
          const SizedBox(height: 4),
          Text(
            today == null
                ? 'No prices recorded yet for this edition.'
                : 'Day 1 recorded: ${num0(today!.min)} – ${num0(today!.max)} EGP. Come back tomorrow for the first line.',
            style: const TextStyle(color: Palette.muted, fontSize: 12.5),
            textAlign: TextAlign.center,
          ),
        ]),
      );
}

class _RangeChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _RangeChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: selected ? Palette.blue : Palette.surface2,
            borderRadius: BorderRadius.circular(9),
          ),
          child: Text(label,
              style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w700, color: selected ? Colors.white : Palette.muted)),
        ),
      );
}

class _Legend extends StatelessWidget {
  final Color c;
  final String t;
  const _Legend(this.c, this.t);

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 5),
        Text(t, style: const TextStyle(color: Palette.muted, fontSize: 11.5, fontWeight: FontWeight.w600)),
      ]);
}
