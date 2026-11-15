import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../data/repo.dart';
import 'listing_sheet.dart';
import 'theme.dart';

Future<void> openUrl(BuildContext context, String url) async {
  if (url.isEmpty) return;
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open the link')));
  }
}

/// Digital / Disc switch shown on top of the main tabs.
class ModelSwitch extends StatelessWidget {
  final Repo repo;
  const ModelSwitch({super.key, required this.repo});

  @override
  Widget build(BuildContext context) {
    Widget seg(Model m, String label, IconData icon) {
      final sel = repo.model == m;
      return Expanded(
        child: GestureDetector(
          onTap: () => repo.setModel(m),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOut,
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              gradient: sel ? Palette.heroGradient : null,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 18, color: sel ? Colors.white : Palette.muted),
                const SizedBox(width: 8),
                Text(label,
                    style: TextStyle(
                        fontWeight: FontWeight.w700, color: sel ? Colors.white : Palette.muted, fontSize: 15)),
              ],
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Palette.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Palette.line),
      ),
      child: Row(children: [
        seg(Model.digital, 'Slim Digital', Icons.cloud_download_rounded),
        seg(Model.disc, 'Slim Disc (CD)', Icons.album_rounded),
      ]),
    );
  }
}

class ChangeBadge extends StatelessWidget {
  final int? change;
  final bool small;
  const ChangeBadge(this.change, {super.key, this.small = false});

  @override
  Widget build(BuildContext context) {
    if (change == null || change == 0) {
      return Text(change == null ? 'new' : 'same',
          style: TextStyle(color: Palette.muted, fontSize: small ? 11 : 12, fontWeight: FontWeight.w600));
    }
    final up = change! > 0;
    final c = up ? Palette.up : Palette.down;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: small ? 6 : 8, vertical: 3),
      decoration: BoxDecoration(color: c.withValues(alpha: .14), borderRadius: BorderRadius.circular(8)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(up ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded, size: small ? 11 : 13, color: c),
        const SizedBox(width: 2),
        Text(num0(change!.abs()),
            style: TextStyle(color: c, fontSize: small ? 11 : 12, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}

class Tag extends StatelessWidget {
  final String text;
  final Color color;
  const Tag(this.text, {super.key, this.color = Palette.muted});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .12),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withValues(alpha: .35)),
        ),
        child: Text(text, style: TextStyle(color: color, fontSize: 10.5, fontWeight: FontWeight.w700)),
      );
}

Color storeColor(String s) {
  const colors = [
    Color(0xFF2E6BFF), Color(0xFFFFB547), Color(0xFF2BD99F), Color(0xFFB57BFF),
    Color(0xFFFF7A59), Color(0xFF00C2FF), Color(0xFFFF5CA8), Color(0xFF9BE15D),
  ];
  return colors[s.codeUnits.fold<int>(0, (a, b) => a + b) % colors.length];
}

class StoreAvatar extends StatelessWidget {
  final String store;
  final double size;
  const StoreAvatar(this.store, {super.key, this.size = 42});

  @override
  Widget build(BuildContext context) {
    final c = storeColor(store);
    final letters = store.replaceAll(RegExp(r'[^A-Za-z0-9]'), ' ').trim().split(RegExp(r'\s+'));
    final txt = letters.isEmpty || letters.first.isEmpty
        ? '?'
        : (letters.length > 1 && letters[1].isNotEmpty ? letters[0][0] + letters[1][0] : letters[0].substring(0, letters[0].length.clamp(1, 2)));
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: c.withValues(alpha: .16),
        borderRadius: BorderRadius.circular(size * .32),
        border: Border.all(color: c.withValues(alpha: .4)),
      ),
      child: Text(txt.toUpperCase(),
          style: TextStyle(color: c, fontWeight: FontWeight.w800, fontSize: size * .34, letterSpacing: -.5)),
    );
  }
}

List<Widget> listingTags(Listing l) => [
      if (l.manual) const Tag('Logged by you', color: Palette.amber),
      if (l.bundle) const Tag('Bundle', color: Color(0xFFB57BFF)),
      if (l.region != null) Tag(l.region!, color: Palette.cyan),
      if (!l.slimConfirmed) const Tag('Slim not stated', color: Palette.amber),
      if (l.oldPrice != null) Tag('was ${compact(l.oldPrice!)}', color: Palette.muted),
    ];

class OfferTile extends StatelessWidget {
  final Listing l;
  final Repo repo;
  final int? rank;
  final bool highlightLowest;
  const OfferTile(this.l, this.repo, {super.key, this.rank, this.highlightLowest = false});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: () => showListingSheet(context, l, repo),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Palette.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: highlightLowest ? Palette.down.withValues(alpha: .6) : Palette.line),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          StoreAvatar(l.store),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(l.where,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14.5)),
              const SizedBox(height: 2),
              Text(l.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Palette.muted, fontSize: 12.5, height: 1.3)),
              const SizedBox(height: 6),
              Wrap(spacing: 5, runSpacing: 4, children: listingTags(l)),
            ]),
          ),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(num0(l.price), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17, letterSpacing: -.3)),
            const Text('EGP', style: TextStyle(color: Palette.muted, fontSize: 10.5, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            if (!l.manual) ChangeBadge(l.change, small: true),
          ]),
        ]),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  final String text;
  final Widget? trailing;
  const SectionTitle(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 22, 4, 10),
        child: Row(children: [
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, letterSpacing: -.2)),
          ),
          if (trailing != null) trailing!,
        ]),
      );
}
