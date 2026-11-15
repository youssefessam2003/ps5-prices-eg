import 'dart:math';

enum Model { digital, disc }

Model modelFrom(String? s) => s == 'digital' ? Model.digital : Model.disc;

class Listing {
  final String id, source, store, title, url;
  final String? seller, region;
  final int price;
  final int? oldPrice, prevPrice;
  final bool inStock, bundle, slimConfirmed, manual;
  final Model model;
  final DateTime? seenAt;
  final String? firstSeen;

  Listing({
    required this.id,
    required this.source,
    required this.store,
    required this.title,
    required this.url,
    required this.price,
    required this.model,
    this.seller,
    this.region,
    this.oldPrice,
    this.prevPrice,
    this.inStock = true,
    this.bundle = false,
    this.slimConfirmed = true,
    this.manual = false,
    this.seenAt,
    this.firstSeen,
  });

  factory Listing.fromJson(Map<String, dynamic> j) => Listing(
        id: j['id'],
        source: j['source'],
        store: j['store'],
        title: j['title'] ?? '',
        url: j['url'] ?? '',
        price: (j['price'] as num).round(),
        oldPrice: (j['old_price'] as num?)?.round(),
        prevPrice: (j['prev_price'] as num?)?.round(),
        model: modelFrom(j['model']),
        seller: j['seller'],
        region: j['region'],
        inStock: j['in_stock'] ?? true,
        bundle: j['bundle'] ?? false,
        slimConfirmed: j['slim_confirmed'] ?? true,
        manual: j['manual'] ?? false,
        seenAt: DateTime.tryParse(j['seen_at'] ?? ''),
        firstSeen: j['first_seen'],
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'source': source,
        'store': store,
        'title': title,
        'url': url,
        'price': price,
        'model': model.name,
        'seller': seller,
        'region': region,
        'in_stock': inStock,
        'bundle': bundle,
        'slim_confirmed': slimConfirmed,
        'manual': manual,
        'seen_at': seenAt?.toIso8601String(),
      };

  /// Store + seller, e.g. "Noon · EgyGamer".
  String get where => seller == null || seller!.isEmpty ? store : '$store · $seller';

  int? get change => prevPrice == null ? null : price - prevPrice!;
  bool get isNew => prevPrice == null;
}

class Stats {
  final int count, stores, min, max, median, avg, common, commonCount;
  final Listing? cheapest, priciest;

  Stats({
    required this.count,
    required this.stores,
    required this.min,
    required this.max,
    required this.median,
    required this.avg,
    required this.common,
    required this.commonCount,
    this.cheapest,
    this.priciest,
  });

  static Stats? of(List<Listing> items) {
    if (items.isEmpty) return null;
    final prices = items.map((e) => e.price).toList()..sort();
    final mid = prices.length ~/ 2;
    final median = prices.length.isOdd ? prices[mid] : ((prices[mid - 1] + prices[mid]) / 2).round();
    final buckets = <int, int>{};
    for (final p in prices) {
      final b = (p / 500).round() * 500;
      buckets[b] = (buckets[b] ?? 0) + 1;
    }
    final common = buckets.entries.reduce((a, b) => b.value > a.value || (b.value == a.value && b.key < a.key) ? b : a);
    return Stats(
      count: prices.length,
      stores: items.map((e) => e.source).toSet().length,
      min: prices.first,
      max: prices.last,
      median: median,
      avg: (prices.reduce((a, b) => a + b) / prices.length).round(),
      common: common.key,
      commonCount: common.value,
      cheapest: items.reduce((a, b) => b.price < a.price ? b : a),
      priciest: items.reduce((a, b) => b.price > a.price ? b : a),
    );
  }

  factory Stats.fromJson(Map<String, dynamic> j) => Stats(
        count: j['count'],
        stores: j['stores'],
        min: j['min'],
        max: j['max'],
        median: j['median'],
        avg: j['avg'],
        common: j['common'],
        commonCount: j['common_count'],
      );
}

class SourceStatus {
  final String id, name, kind, url;
  final String status; // ok | error | manual | missing
  final String? error;
  final int count, inStock;
  final DateTime? fetchedAt;

  SourceStatus({
    required this.id,
    required this.name,
    required this.kind,
    required this.url,
    required this.status,
    this.error,
    this.count = 0,
    this.inStock = 0,
    this.fetchedAt,
  });
}

class DayStats {
  final DateTime date;
  final Map<String, Stats?> stats; // key: "digital/console", "disc/all", ...
  DayStats(this.date, this.stats);

  Stats? get(Model m, bool bundles) => stats['${m.name}/${bundles ? 'all' : 'console'}'];
}

class ListingSeries {
  final String store, title;
  final String? seller;
  final List<(DateTime, int, bool)> points;
  ListingSeries(this.store, this.title, this.seller, this.points);
}

class Snapshot {
  final String date;
  final DateTime? generatedAt;
  final List<Listing> listings;
  final List<SourceStatus> sources;
  final List<DayStats> days;
  final Map<String, ListingSeries> series;

  Snapshot({
    required this.date,
    required this.generatedAt,
    required this.listings,
    required this.sources,
    required this.days,
    required this.series,
  });

  factory Snapshot.parse(Map<String, dynamic> latest, Map<String, dynamic>? history) {
    final listings = (latest['listings'] as List).map((e) => Listing.fromJson(e)).toList();
    final status = (latest['sources'] as Map<String, dynamic>? ?? {});
    final sources = <SourceStatus>[];
    for (final d in (latest['directory'] as List? ?? [])) {
      final s = status[d['id']] as Map<String, dynamic>?;
      sources.add(SourceStatus(
        id: d['id'],
        name: d['name'],
        kind: d['kind'],
        url: d['url'],
        status: d['kind'] == 'manual' ? 'manual' : (s?['status'] ?? 'missing'),
        error: s?['error'],
        count: s?['count'] ?? 0,
        inStock: s?['in_stock'] ?? 0,
        fetchedAt: DateTime.tryParse(s?['fetched_at'] ?? ''),
      ));
    }
    final days = <DayStats>[];
    final series = <String, ListingSeries>{};
    if (history != null) {
      for (final d in history['days'] as List) {
        final m = <String, Stats?>{};
        final st = d['stats'] as Map<String, dynamic>;
        for (final model in ['digital', 'disc']) {
          for (final scope in ['console', 'all']) {
            final v = st[model]?[scope];
            m['$model/$scope'] = v == null ? null : Stats.fromJson(v);
          }
        }
        days.add(DayStats(DateTime.parse(d['date']), m));
      }
      (history['listings'] as Map<String, dynamic>).forEach((id, v) {
        series[id] = ListingSeries(
          v['store'] ?? '',
          v['title'] ?? '',
          v['seller'],
          [for (final p in v['points'] as List) (DateTime.parse(p[0]), (p[1] as num).round(), p[2] == 1)],
        );
      });
    }
    return Snapshot(
      date: latest['date'],
      generatedAt: DateTime.tryParse(latest['generated_at'] ?? ''),
      listings: listings,
      sources: sources,
      days: days,
      series: series,
    );
  }
}

/// A price the user logged from a Facebook page, a shop visit, etc.
class ManualEntry {
  final String id, store, note;
  final Model model;
  final int price;
  final bool bundle;
  final DateTime at;
  final String url;

  ManualEntry({
    required this.id,
    required this.store,
    required this.model,
    required this.price,
    required this.at,
    this.bundle = false,
    this.note = '',
    this.url = '',
  });

  factory ManualEntry.fromJson(Map<String, dynamic> j) => ManualEntry(
        id: j['id'],
        store: j['store'],
        model: modelFrom(j['model']),
        price: j['price'],
        at: DateTime.parse(j['at']),
        bundle: j['bundle'] ?? false,
        note: j['note'] ?? '',
        url: j['url'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'store': store,
        'model': model.name,
        'price': price,
        'at': at.toIso8601String(),
        'bundle': bundle,
        'note': note,
        'url': url,
      };

  Listing toListing() => Listing(
        id: 'manual:$id',
        source: 'manual',
        store: store,
        title: note.isEmpty ? 'PS5 Slim ${model == Model.digital ? 'Digital' : 'Disc'} (logged by you)' : note,
        url: url,
        price: price,
        model: model,
        bundle: bundle,
        manual: true,
        seenAt: at,
      );
}

String newId() => DateTime.now().microsecondsSinceEpoch.toRadixString(36) + Random().nextInt(999).toString();
