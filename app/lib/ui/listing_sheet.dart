import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/models.dart';
import '../data/repo.dart';
import 'theme.dart';
import 'widgets.dart';

void showListingSheet(BuildContext context, Listing l, Repo repo) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (_) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: .62,
      maxChildSize: .92,
      builder: (ctx, sc) => _Sheet(l: l, repo: repo, controller: sc),
    ),
  );
}

class _Sheet extends StatelessWidget {
  final Listing l;
  final Repo repo;
  final ScrollController controller;
  const _Sheet({required this.l, required this.repo, required this.controller});

  @override
  Widget build(BuildContext context) {
    final series = repo.snapshot?.series[l.id];
    final pts = series?.points ?? [];
    final s = repo.stats();
    final rank = repo.offers().indexWhere((e) => e.id == l.id) + 1;
    return ListView(controller: controller, padding: const EdgeInsets.fromLTRB(20, 0, 20, 28), children: [
      Row(children: [
        StoreAvatar(l.store, size: 48),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l.store, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
            if (l.seller != null) Text('Seller: ${l.seller}', style: const TextStyle(color: Palette.muted)),
          ]),
        ),
      ]),
      const SizedBox(height: 14),
      Text(l.title, style: const TextStyle(fontSize: 14.5, height: 1.35)),
      const SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 6, children: listingTags(l)),
      const SizedBox(height: 18),
      Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Text(num0(l.price), style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w900, letterSpacing: -1)),
        const Padding(
          padding: EdgeInsets.only(left: 6, bottom: 6),
          child: Text('EGP', style: TextStyle(color: Palette.muted, fontWeight: FontWeight.w800)),
        ),
        const Spacer(),
        if (!l.manual) ChangeBadge(l.change),
      ]),
      if (s != null && rank > 0)
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            rank == 1
                ? 'Cheapest of ${s.count} offers today'
                : '#$rank of ${s.count} · ${num0(l.price - s.min)} EGP above the lowest',
            style: TextStyle(color: rank == 1 ? Palette.down : Palette.muted, fontWeight: FontWeight.w600),
          ),
        ),
      const SizedBox(height: 6),
      Text(
        l.manual
            ? 'Logged by you ${ago(l.seenAt)}'
            : 'In stock when checked ${ago(l.seenAt)}${l.firstSeen != null ? ' · tracked since ${l.firstSeen}' : ''}',
        style: const TextStyle(color: Palette.muted, fontSize: 12.5),
      ),
      const SizedBox(height: 18),
      if (pts.length >= 2) ...[
        const Text('This offer\'s price history', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
        const SizedBox(height: 12),
        SizedBox(height: 160, child: _miniChart(pts)),
        const SizedBox(height: 18),
      ],
      if (l.url.isNotEmpty)
        FilledButton.icon(
          onPressed: () => openUrl(context, l.url),
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
          icon: const Icon(Icons.open_in_new_rounded),
          label: Text('Open on ${l.store}', style: const TextStyle(fontWeight: FontWeight.w800)),
        ),
      if (l.manual) ...[
        const SizedBox(height: 10),
        OutlinedButton.icon(
          onPressed: () {
            repo.removeManual(l.id.replaceFirst('manual:', ''));
            Navigator.pop(context);
          },
          icon: const Icon(Icons.delete_outline_rounded),
          label: const Text('Delete this logged price'),
        ),
      ],
    ]);
  }

  Widget _miniChart(List<(DateTime, int, bool)> pts) {
    final t0 = pts.first.$1;
    final ys = pts.map((p) => p.$2);
    final lo = ys.reduce(min).toDouble(), hi = ys.reduce(max).toDouble();
    final pad = max(300.0, (hi - lo) * .2);
    return LineChart(LineChartData(
      minY: lo - pad,
      maxY: hi + pad,
      gridData: const FlGridData(show: false),
      borderData: FlBorderData(show: false),
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(),
        rightTitles: const AxisTitles(),
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 40,
            getTitlesWidget: (v, m) => v == m.min || v == m.max
                ? const SizedBox()
                : Text(compact(v.round()), style: const TextStyle(color: Palette.muted, fontSize: 10)),
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 22,
            interval: max(1, (pts.last.$1.difference(t0).inDays / 3).ceilToDouble()),
            getTitlesWidget: (v, m) => Text(DateFormat('d MMM').format(t0.add(Duration(days: v.round()))),
                style: const TextStyle(color: Palette.muted, fontSize: 10)),
          ),
        ),
      ),
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (_) => Palette.surface2,
          getTooltipItems: (s) => [
            for (final x in s)
              LineTooltipItem(
                '${DateFormat('d MMM').format(t0.add(Duration(days: x.x.round())))}\n${num0(x.y.round())}',
                const TextStyle(fontWeight: FontWeight.w700),
              ),
          ],
        ),
      ),
      lineBarsData: [
        LineChartBarData(
          spots: [for (final p in pts) FlSpot(p.$1.difference(t0).inDays.toDouble(), p.$2.toDouble())],
          isStepLineChart: true,
          color: Palette.cyan,
          barWidth: 2.5,
          dotData: FlDotData(
            getDotPainter: (spot, _, __, i) => FlDotCirclePainter(
              radius: 3,
              color: pts[i].$3 ? Palette.cyan : Palette.up,
              strokeWidth: 0,
            ),
          ),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [Palette.cyan.withValues(alpha: .2), Palette.cyan.withValues(alpha: 0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
      ],
    ));
  }
}
