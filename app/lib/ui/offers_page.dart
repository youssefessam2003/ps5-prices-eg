import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/repo.dart';
import 'theme.dart';
import 'widgets.dart';
import 'price_check_status.dart';

enum Sort { cheapest, priciest, biggestDrop }

class OffersPage extends StatefulWidget {
  final Repo repo;
  const OffersPage({super.key, required this.repo});

  @override
  State<OffersPage> createState() => _OffersPageState();
}

class _OffersPageState extends State<OffersPage> {
  String query = '';
  Sort sort = Sort.cheapest;
  final Set<String> stores = {};

  @override
  Widget build(BuildContext context) {
    final repo = widget.repo;
    final all = repo.offers();
    final storeNames = (all.map((e) => e.store).toSet().toList()..sort());
    stores.removeWhere((s) => !storeNames.contains(s));
    var list = all.where((l) {
      if (stores.isNotEmpty && !stores.contains(l.store)) return false;
      if (query.isEmpty) return true;
      final q = query.toLowerCase();
      return l.title.toLowerCase().contains(q) || l.where.toLowerCase().contains(q);
    }).toList();
    switch (sort) {
      case Sort.cheapest:
        list.sort((a, b) => a.price.compareTo(b.price));
      case Sort.priciest:
        list.sort((a, b) => b.price.compareTo(a.price));
      case Sort.biggestDrop:
        list.sort((a, b) => (a.change ?? 0).compareTo(b.change ?? 0));
    }
    final s = Stats.of(list);

    return CustomScrollView(slivers: [
      SliverAppBar(
        floating: true,
        title: const Text('All offers', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 22)),
        actions: [
          RefreshPricesButton(repo: repo),
          PopupMenuButton<Sort>(
            icon: const Icon(Icons.sort_rounded),
            initialValue: sort,
            onSelected: (v) => setState(() => sort = v),
            itemBuilder: (_) => const [
              PopupMenuItem(value: Sort.cheapest, child: Text('Cheapest first')),
              PopupMenuItem(value: Sort.priciest, child: Text('Most expensive first')),
              PopupMenuItem(value: Sort.biggestDrop, child: Text('Biggest drop since yesterday')),
            ],
          ),
        ],
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
        sliver: SliverList.list(children: [
          PriceCheckStatus(repo: repo),
          ModelSwitch(repo: repo),
          const SizedBox(height: 10),
          TextField(
            onChanged: (v) => setState(() => query = v.trim()),
            decoration: const InputDecoration(
              hintText: 'Search store, seller or title',
              prefixIcon: Icon(Icons.search_rounded),
              isDense: true,
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 38,
            child: ListView(scrollDirection: Axis.horizontal, children: [
              FilterChip(
                label: const Text('Bundles'),
                selected: repo.includeBundles,
                onSelected: repo.setBundles,
              ),
              const SizedBox(width: 6),
              for (final st in storeNames) ...[
                FilterChip(
                  label: Text(st),
                  selected: stores.contains(st),
                  onSelected: (v) => setState(() => v ? stores.add(st) : stores.remove(st)),
                ),
                const SizedBox(width: 6),
              ],
            ]),
          ),
          const SizedBox(height: 10),
          if (s != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Text(
                '${s.count} in-stock offers · ${num0(s.min)} → ${num0(s.max)} EGP',
                style: const TextStyle(color: Palette.muted, fontWeight: FontWeight.w600, fontSize: 12.5),
              ),
            ),
          const SizedBox(height: 8),
        ]),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 28),
        sliver: list.isEmpty
            ? const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.all(40),
                  child: Center(child: Text('Nothing matches', style: TextStyle(color: Palette.muted))),
                ),
              )
            : SliverList.separated(
                itemCount: list.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (_, i) => OfferTile(list[i], repo,
                    highlightLowest: sort == Sort.cheapest && i == 0 && stores.isEmpty && query.isEmpty),
              ),
      ),
    ]);
  }
}
