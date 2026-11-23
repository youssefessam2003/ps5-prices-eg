import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/models.dart';
import '../data/repo.dart';
import 'theme.dart';
import 'widgets.dart';
import 'price_check_status.dart';

class StoresPage extends StatelessWidget {
  final Repo repo;
  const StoresPage({super.key, required this.repo});

  @override
  Widget build(BuildContext context) {
    final src = repo.snapshot?.sources ?? [];
    final live = src.where((s) => s.kind != 'manual').toList()
      ..sort((a, b) => b.inStock.compareTo(a.inStock) != 0 ? b.inStock.compareTo(a.inStock) : a.name.compareTo(b.name));
    final manual = src.where((s) => s.kind == 'manual').toList();
    final ok = live.where((s) => s.status == 'ok').length;
    final offersByStore = <String, int>{};
    for (final l in repo.snapshot?.listings ?? <Listing>[]) {
      if (l.inStock) offersByStore[l.source] = (offersByStore[l.source] ?? 0) + 1;
    }

    return CustomScrollView(slivers: [
      SliverAppBar(
        floating: true,
        title: const Text('Stores', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 22)),
        actions: [
          RefreshPricesButton(repo: repo),
          IconButton(
            tooltip: 'Data source',
            icon: const Icon(Icons.tune_rounded),
            onPressed: () => _settings(context, repo),
          ),
        ],
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
        sliver: SliverList.list(children: [
          PriceCheckStatus(repo: repo),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                _big('$ok/${live.length}', 'checked today'),
                _big('${offersByStore.values.fold<int>(0, (a, b) => a + b)}', 'in-stock offers'),
                _big('${repo.manual.length}', 'logged by you'),
              ]),
            ),
          ),
          const SectionTitle('Checked automatically every day'),
          for (final s in live) ...[
            _SourceTile(s: s, offers: offersByStore[s.id] ?? 0),
            const SizedBox(height: 8),
          ],
          const SectionTitle('Social pages, marketplaces & shops'),
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 0, 4, 10),
            child: Text(
              'Facebook pages, Marketplace, Dubizzle and walk-in shops don\'t publish prices a machine can read. '
              'Open them from here and tap “Log a price” — your entries count in the stats for 3 days.',
              style: TextStyle(color: Palette.muted, fontSize: 12.5, height: 1.4),
            ),
          ),
          for (final s in manual) ...[
            _SourceTile(s: s, offers: 0, onLog: () => showLogSheet(context, repo, store: s.name, url: s.url)),
            const SizedBox(height: 8),
          ],
          if (repo.manual.isNotEmpty) ...[
            const SectionTitle('Your logged prices'),
            for (final e in repo.manual.reversed) ...[
              OfferTile(e.toListing(), repo),
              const SizedBox(height: 8),
            ],
          ],
        ]),
      ),
    ]);
  }

  Widget _big(String v, String l) => Expanded(
        child: Column(children: [
          Text(v, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
          Text(l, style: const TextStyle(color: Palette.muted, fontSize: 11.5)),
        ]),
      );

  void _settings(BuildContext context, Repo repo) {
    final c = TextEditingController(text: repo.dataUrl);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.of(ctx).viewInsets.bottom + 24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Price data address', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
          const SizedBox(height: 6),
          const Text('Folder that holds latest.json and history.json (published by the daily collector).',
              style: TextStyle(color: Palette.muted)),
          const SizedBox(height: 14),
          TextField(controller: c, maxLines: 2, style: const TextStyle(fontSize: 13)),
          const SizedBox(height: 14),
          Row(children: [
            TextButton(onPressed: () => c.text = defaultDataUrl, child: const Text('Reset')),
            const Spacer(),
            FilledButton(
              onPressed: () {
                repo.setDataUrl(c.text);
                Navigator.pop(ctx);
              },
              child: const Text('Save & reload'),
            ),
          ]),
        ]),
      ),
    );
  }
}

class _SourceTile extends StatelessWidget {
  final SourceStatus s;
  final int offers;
  final VoidCallback? onLog;
  const _SourceTile({required this.s, required this.offers, this.onLog});

  @override
  Widget build(BuildContext context) {
    final (Color c, String label) = switch (s.status) {
      'ok' => offers > 0 ? (Palette.down, '$offers in stock') : (Palette.muted, 'none in stock'),
      'error' => (Palette.up, 'couldn\'t check today'),
      'manual' => (Palette.amber, 'log manually'),
      _ => (Palette.muted, 'not checked yet'),
    };
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: () => openUrl(context, s.url),
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
        decoration: BoxDecoration(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Palette.line),
        ),
        child: Row(children: [
          StoreAvatar(s.name, size: 38),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(s.name, style: const TextStyle(fontWeight: FontWeight.w800)),
              const SizedBox(height: 3),
              Row(children: [
                Container(width: 7, height: 7, decoration: BoxDecoration(color: c, shape: BoxShape.circle)),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    s.status == 'ok' || s.status == 'error' ? '$label · ${ago(s.fetchedAt)}' : label,
                    style: TextStyle(color: c, fontSize: 12, fontWeight: FontWeight.w600),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ]),
            ]),
          ),
          if (onLog != null)
            TextButton.icon(onPressed: onLog, icon: const Icon(Icons.add_rounded, size: 18), label: const Text('Log a price'))
          else
            const Icon(Icons.open_in_new_rounded, size: 18, color: Palette.muted),
          const SizedBox(width: 6),
        ]),
      ),
    );
  }
}

void showLogSheet(BuildContext context, Repo repo, {String store = '', String url = ''}) {
  final storeC = TextEditingController(text: store);
  final priceC = TextEditingController();
  final noteC = TextEditingController();
  final urlC = TextEditingController(text: url);
  var model = repo.model;
  var bundle = false;
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setS) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.of(ctx).viewInsets.bottom + 24),
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Log a price you saw', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
            const SizedBox(height: 4),
            const Text('From a Facebook page, a shop visit, a WhatsApp message…', style: TextStyle(color: Palette.muted)),
            const SizedBox(height: 16),
            SegmentedButton<Model>(
              segments: const [
                ButtonSegment(value: Model.digital, label: Text('Slim Digital')),
                ButtonSegment(value: Model.disc, label: Text('Slim Disc')),
              ],
              selected: {model},
              onSelectionChanged: (v) => setS(() => model = v.first),
            ),
            const SizedBox(height: 12),
            TextField(controller: storeC, decoration: const InputDecoration(labelText: 'Store / page name')),
            const SizedBox(height: 10),
            TextField(
              controller: priceC,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(labelText: 'Price (EGP)', suffixText: 'EGP'),
            ),
            const SizedBox(height: 10),
            TextField(controller: noteC, decoration: const InputDecoration(labelText: 'Note (optional)')),
            const SizedBox(height: 10),
            TextField(controller: urlC, decoration: const InputDecoration(labelText: 'Link (optional)')),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: bundle,
              onChanged: (v) => setS(() => bundle = v),
              title: const Text('Bundle (extra controller / game)'),
            ),
            const SizedBox(height: 6),
            FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
              onPressed: () {
                final p = int.tryParse(priceC.text);
                if (p == null || p < 10000 || storeC.text.trim().isEmpty) {
                  ScaffoldMessenger.of(ctx).showSnackBar(
                      const SnackBar(content: Text('Enter the store name and a price in EGP')));
                  return;
                }
                repo.addManual(ManualEntry(
                  id: newId(),
                  store: storeC.text.trim(),
                  model: model,
                  price: p,
                  at: DateTime.now(),
                  bundle: bundle,
                  note: noteC.text.trim(),
                  url: urlC.text.trim(),
                ));
                Navigator.pop(ctx);
              },
              child: const Text('Save price', style: TextStyle(fontWeight: FontWeight.w800)),
            ),
          ]),
        ),
      ),
    ),
  );
}
