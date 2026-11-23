import 'dart:math';

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repo.dart';
import 'theme.dart';
import 'trend_chart.dart';
import 'widgets.dart';
import 'price_check_status.dart';

class HomePage extends StatelessWidget {
  final Repo repo;
  final VoidCallback onSeeAll;
  const HomePage({super.key, required this.repo, required this.onSeeAll});

  @override
  Widget build(BuildContext context) {
    final snap = repo.snapshot;
    final offers = repo.offers();
    final s = Stats.of(offers);
    final prevDay = _previousDayStats(snap, repo);

    return RefreshIndicator(
      onRefresh: repo.refresh,
      child: CustomScrollView(slivers: [
        SliverAppBar(
          floating: true,
          toolbarHeight: 72,
          title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('PS5 Prices · Egypt', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 22, letterSpacing: -.5)),
            const SizedBox(height: 2),
            Text(
              snap == null
                  ? 'Loading…'
                  : 'Checked ${ago(snap.generatedAt)} · ${snap.sources.where((e) => e.status == 'ok').length} sources live',
              style: const TextStyle(color: Palette.muted, fontSize: 12.5),
            ),
          ]),
          actions: [
            RefreshPricesButton(repo: repo),
          ],
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
          sliver: SliverList.list(children: [
            PriceCheckStatus(repo: repo),
            ModelSwitch(repo: repo),
            const SizedBox(height: 10),
            _FilterRow(repo: repo),
            const SizedBox(height: 14),
            if (s == null)
              const _Empty()
            else ...[
              _Hero(s: s, prev: prevDay, repo: repo),
              const SizedBox(height: 12),
              _StatGrid(s: s),
              const SizedBox(height: 12),
              _Distribution(offers: offers, s: s),
            ],
            const SizedBox(height: 12),
            if (snap != null) TrendCard(days: snap.days, model: repo.model, bundles: repo.includeBundles),
            if (s != null) ...[
              SectionTitle('Cheapest right now',
                  trailing: TextButton(onPressed: onSeeAll, child: Text('All ${s.count} offers'))),
              for (final (i, l) in offers.take(5).indexed) ...[
                OfferTile(l, repo, rank: i + 1, highlightLowest: i == 0),
                const SizedBox(height: 8),
              ],
            ],
          ]),
        ),
      ]),
    );
  }

  Stats? _previousDayStats(Snapshot? snap, Repo repo) {
    if (snap == null || snap.days.length < 2) return null;
    final today = DateTime.parse(snap.date);
    final prev = snap.days.lastWhere((d) => d.date.isBefore(today), orElse: () => snap.days.first);
    if (!prev.date.isBefore(today)) return null;
    return prev.get(repo.model, repo.includeBundles);
  }
}

class _FilterRow extends StatelessWidget {
  final Repo repo;
  const _FilterRow({required this.repo});

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          FilterChip(
            label: const Text('Include bundles'),
            selected: repo.includeBundles,
            onSelected: repo.setBundles,
            avatar: repo.includeBundles ? null : const Icon(Icons.add_rounded, size: 16),
          ),
          const SizedBox(width: 8),
          FilterChip(
            label: const Text('“Slim” not stated'),
            selected: repo.includeUnconfirmedSlim,
            onSelected: repo.setUnconfirmed,
            tooltip: 'Also count listings that don\'t say Slim in the title (could be the older model).',
          ),
          if (repo.manual.isNotEmpty) ...[
            const SizedBox(width: 8),
            FilterChip(label: const Text('My logged prices'), selected: repo.includeManual, onSelected: repo.setManualOn),
          ],
        ]),
      );
}

class _Hero extends StatelessWidget {
  final Stats s;
  final Stats? prev;
  final Repo repo;
  const _Hero({required this.s, required this.prev, required this.repo});

  @override
  Widget build(BuildContext context) {
    final l = s.cheapest!;
    final diff = prev == null ? null : s.min - prev!.min;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: Palette.heroGradient,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [BoxShadow(color: Palette.blue.withValues(alpha: .35), blurRadius: 30, offset: const Offset(0, 12))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.local_offer_rounded, color: Colors.white70, size: 16),
          const SizedBox(width: 6),
          const Text('LOWEST PRICE TODAY',
              style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 1)),
          const Spacer(),
          if (diff != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(color: Colors.black.withValues(alpha: .2), borderRadius: BorderRadius.circular(10)),
              child: Text(
                diff == 0 ? 'Same as yesterday' : '${diff > 0 ? '▲' : '▼'} ${num0(diff.abs())} vs yesterday',
                style: const TextStyle(color: Colors.white, fontSize: 11.5, fontWeight: FontWeight.w700),
              ),
            ),
        ]),
        const SizedBox(height: 10),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(num0(s.min),
              style: const TextStyle(color: Colors.white, fontSize: 44, fontWeight: FontWeight.w900, letterSpacing: -1.5, height: 1)),
          const SizedBox(width: 6),
          const Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text('EGP', style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w800)),
          ),
        ]),
        const SizedBox(height: 10),
        Text(l.where, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 15)),
        const SizedBox(height: 2),
        Text(l.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white70, fontSize: 12.5)),
        const SizedBox(height: 14),
        Row(children: [
          FilledButton.icon(
            onPressed: l.url.isEmpty ? null : () => openUrl(context, l.url),
            style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: const Color(0xFF0B2A8F)),
            icon: const Icon(Icons.open_in_new_rounded, size: 18),
            label: const Text('Open offer', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
          const SizedBox(width: 10),
          Text('${s.count} offers · ${s.stores} stores',
              style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w600, fontSize: 12.5)),
        ]),
      ]),
    );
  }
}

class _StatGrid extends StatelessWidget {
  final Stats s;
  const _StatGrid({required this.s});

  @override
  Widget build(BuildContext context) {
    Widget cell(String label, String value, String sub, IconData icon, Color c) => Expanded(
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Palette.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Palette.line),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(icon, size: 15, color: c),
                const SizedBox(width: 5),
                Flexible(
                  child: Text(label,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Palette.muted, fontSize: 12, fontWeight: FontWeight.w700)),
                ),
              ]),
              const SizedBox(height: 6),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, letterSpacing: -.5)),
              ),
              Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Palette.muted, fontSize: 11.5)),
            ]),
          ),
        );
    return Column(children: [
      Row(children: [
        cell('Highest', num0(s.max), s.priciest?.store ?? '', Icons.trending_up_rounded, Palette.up),
        const SizedBox(width: 10),
        cell('Most common', '≈ ${num0(s.common)}', '${s.commonCount} of ${s.count} offers', Icons.groups_rounded, Palette.amber),
      ]),
      const SizedBox(height: 10),
      Row(children: [
        cell('Median', num0(s.median), 'half are cheaper', Icons.align_horizontal_center_rounded, Palette.cyan),
        const SizedBox(width: 10),
        cell('Spread', num0(s.max - s.min), 'highest − lowest', Icons.straighten_rounded, const Color(0xFFB57BFF)),
      ]),
    ]);
  }
}

/// Histogram: how many offers fall in each 1,000 EGP band.
class _Distribution extends StatelessWidget {
  final List<Listing> offers;
  final Stats s;
  const _Distribution({required this.offers, required this.s});

  @override
  Widget build(BuildContext context) {
    final step = (s.max - s.min) > 20000 ? 2000 : 1000;
    final start = (s.min ~/ step) * step;
    final n = ((s.max - start) ~/ step) + 1;
    final counts = List.filled(n, 0);
    for (final o in offers) {
      counts[min(n - 1, (o.price - start) ~/ step)]++;
    }
    final peak = counts.reduce(max);
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Where the prices sit', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text('Offers per ${num0(step)} EGP band', style: const TextStyle(color: Palette.muted, fontSize: 12)),
          const SizedBox(height: 14),
          SizedBox(
            height: 110,
            child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              for (var i = 0; i < n; i++)
                Expanded(
                  child: Tooltip(
                    message: '${num0(start + i * step)}–${num0(start + (i + 1) * step - 1)}: ${counts[i]} offers',
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 1.5),
                      child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                        if (counts[i] > 0)
                          Text('${counts[i]}',
                              style: const TextStyle(fontSize: 10, color: Palette.muted, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 3),
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 300),
                          height: counts[i] == 0 ? 3 : 84 * counts[i] / peak,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(5),
                            gradient: counts[i] == peak
                                ? const LinearGradient(
                                    colors: [Palette.amber, Color(0xFFFF8A3D)],
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter)
                                : LinearGradient(
                                    colors: [Palette.blue.withValues(alpha: i == 0 ? 1 : .75), Palette.blue.withValues(alpha: .35)],
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter),
                          ),
                        ),
                      ]),
                    ),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 6),
          Row(children: [
            Text(compact(start), style: const TextStyle(color: Palette.muted, fontSize: 11)),
            const Spacer(),
            Text(compact(start + n * step), style: const TextStyle(color: Palette.muted, fontSize: 11)),
          ]),
        ]),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();

  @override
  Widget build(BuildContext context) => const Card(
        child: Padding(
          padding: EdgeInsets.all(28),
          child: Column(children: [
            Icon(Icons.inventory_2_outlined, size: 40, color: Palette.muted),
            SizedBox(height: 10),
            Text('No in-stock offers match these filters today', style: TextStyle(fontWeight: FontWeight.w700)),
          ]),
        ),
      );
}
