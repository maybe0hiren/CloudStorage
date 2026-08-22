import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import 'api.dart';
import 'models.dart';
import 'dart:typed_data';

const bg = Color(0xFF070B16);
const panel = Color(0xFF0D1424);
const panel2 = Color(0xFF111A2D);
const border = Color(0x1F6E7EA8);
const accent = Color(0xFF7AA2F7);
const purple = Color(0xFF9B8AFB);
const green = Color(0xFF78D7A5);
const red = Color(0xFFE56B7F);
const folderMarkerName = '__overcast_folder__.txt';

void main() => runApp(const OvercastApp());

class OvercastApp extends StatelessWidget {
  const OvercastApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Overcast',
        theme: ThemeData(
          brightness: Brightness.dark,
          scaffoldBackgroundColor: bg,
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(seedColor: accent, brightness: Brightness.dark),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: panel,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(15),
              borderSide: const BorderSide(color: border),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(15),
              borderSide: const BorderSide(color: border),
            ),
          ),
        ),
        home: const OvercastHome(),
      );
}

class OvercastHome extends StatefulWidget {
  const OvercastHome({super.key});
  @override
  State<OvercastHome> createState() => _OvercastHomeState();
}

class _OvercastHomeState extends State<OvercastHome> {
  late OvercastApi api;
  SharedPreferences? prefs;
  String server = 'http://192.168.1.9';
  bool connected = false;
  bool loading = true;
  bool grid = true;
  String path = 'home/';
  String section = 'Home';
  String query = '';
  List<OvercastFile> items = [];
  List<OvercastFile> allFiles = [];
  List<TrashEntry> trash = [];
  StorageInfo? storage;
  Timer? heartbeat;
  final search = TextEditingController();

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    prefs = await SharedPreferences.getInstance();
    server = prefs?.getString('server') ?? server;
    grid = prefs?.getBool('grid') ?? true;
    api = OvercastApi(server);
    await refresh();
    heartbeat = Timer.periodic(const Duration(seconds: 15), (_) => _checkConnection());
  }

  Future<void> _checkConnection() async {
    try {
      final ok = await api.isHealthy();
      if (mounted && ok != connected) setState(() => connected = ok);
    } catch (_) {
      if (mounted && connected) setState(() => connected = false);
    }
  }

  @override
  void dispose() {
    heartbeat?.cancel();
    search.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    if (!mounted) return;
    setState(() => loading = true);
    try {
      final ok = await api.isHealthy();
      if (section == 'Trash') {
        trash = await api.trashList();
        items = [];
        allFiles = [];
      } else {
        // The backend stores folders implicitly as file paths. We fetch the
        // complete metadata set so the client can reconstruct directories.
        allFiles = await api.files();
        items = allFiles
            .where((f) => f.path == path && !_isFolderMarker(f))
            .toList();
      }
      storage = await api.storage();
      if (!mounted) return;
      setState(() {
        connected = ok;
        loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        connected = false;
        loading = false;
      });
      _snack(api.errorMessage(e), error: true);
    }
  }

  bool _isFolderMarker(OvercastFile f) => f.name == folderMarkerName;

  List<OvercastFile> get filtered {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return items;
    return items.where((f) => f.name.toLowerCase().contains(q)).toList();
  }

  List<String> get childFolders {
    final prefix = path.endsWith('/') ? path : '$path/';
    final result = <String>{};
    for (final f in allFiles) {
      if (!f.path.startsWith(prefix) || f.path == prefix) continue;
      final remainder = f.path.substring(prefix.length);
      final slash = remainder.indexOf('/');
      if (slash > 0) result.add(remainder.substring(0, slash));
    }
    final list = result.toList()
      ..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
    return list;
  }

  List<OvercastFile> _filesUnder(String folderPath) {
    final prefix = folderPath.endsWith('/') ? folderPath : '$folderPath/';
    return allFiles.where((f) => f.path.startsWith(prefix)).toList();
  }

  String _joinPath(String base, String name) {
    final b = base.endsWith('/') ? base : '$base/';
    return '$b$name/';
  }

  Future<void> _settings() async {
    final controller = TextEditingController(text: server);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Overcast connection'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Server URL',
            hintText: 'http://192.168.1.9',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Save')),
        ],
      ),
    );
    controller.dispose();
    if (result == null || result.isEmpty) return;
    server = result.replaceFirst(RegExp(r'/*$'), '');
    await prefs?.setString('server', server);
    api = OvercastApi(server);
    path = 'home/';
    section = 'Home';
    await refresh();
  }

  Future<void> _pickUploads() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      withData: false,
    );
    if (result == null) return;
    for (final file in result.files) {
      final p = file.path;
      if (p == null) continue;
      await _uploadOne(p, file.name, destination: path);
    }
    await refresh();
  }

  Future<void> _createFolder() async {
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('New folder'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Folder name',
            hintText: 'Projects',
          ),
          onSubmitted: (v) => Navigator.pop(context, v.trim()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.isEmpty) return;
    if (name == folderMarkerName || name.contains('/') || name.contains('\\')) {
      _snack('That is not a valid folder name.', error: true);
      return;
    }
    final folderPath = _joinPath(path, name);
    try {
      await api.uploadBytes(folderPath, folderMarkerName, Uint8List(0));
      await refresh();
      _snack('Created folder $name');
    } catch (e) {
      _snack('Could not create folder: ${api.errorMessage(e)}', error: true);
    }
  }

  Future<void> _pickFolderUpload() async {
    final folder = await FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Select a folder to upload',
    );
    if (folder == null) return;

    final root = Directory(folder);
    final rootName = root.path
        .split(Platform.pathSeparator)
        .where((p) => p.isNotEmpty)
        .last;
    final files = <File>[];
    final directories = <Directory>[];

    try {
      await for (final entity in root.list(recursive: true, followLinks: false)) {
        if (entity is File) {
          files.add(entity);
        } else if (entity is Directory) {
          directories.add(entity);
        }
      }
    } catch (e) {
      _snack('Could not read folder: $e', error: true);
      return;
    }

    final rootPrefix = root.path.endsWith(Platform.pathSeparator)
        ? root.path
        : '${root.path}${Platform.pathSeparator}';
    final destinationRoot = _joinPath(path, rootName);

    // Upload every real file while preserving its relative directory.
    for (final file in files) {
      final relative = file.path.startsWith(rootPrefix)
          ? file.path.substring(rootPrefix.length)
          : file.uri.pathSegments.last;
      final parts = relative.split(Platform.pathSeparator);
      final fileName = parts.removeLast();
      final relativeDir = parts.join('/');
      final destination = relativeDir.isEmpty
          ? destinationRoot
          : '$destinationRoot$relativeDir/';
      await _uploadOne(file.path, fileName, destination: destination);
    }

    // A directory has no representation in the backend, so empty directories
    // receive one hidden marker text file. The UI never displays the marker.
    final allDirectories = <Directory>[root, ...directories];
    for (final dir in allDirectories) {
      final dirPrefix = dir.path.endsWith(Platform.pathSeparator)
          ? dir.path
          : '${dir.path}${Platform.pathSeparator}';
      final hasFile = files.any((file) =>
          file.path == dir.path || file.path.startsWith(dirPrefix));
      if (hasFile) continue;

      final relative = dir.path == root.path
          ? ''
          : dir.path.substring(rootPrefix.length).replaceAll(Platform.pathSeparator, '/');
      final destination = relative.isEmpty
          ? destinationRoot
          : '$destinationRoot$relative/';
      try {
        await api.uploadBytes(destination, folderMarkerName, Uint8List(0));
      } catch (e) {
        _snack('Could not create empty folder ${dir.path}: ${api.errorMessage(e)}', error: true);
      }
    }

    await refresh();
    _snack('Folder uploaded');
  }

  Future<void> _uploadOne(String filePath, String name, {required String destination}) async {
    double progress = 0;
    final key = 'upload:$name';
    _showProgress(key, 'Uploading $name', progress);
    try {
      await api.upload(destination, filePath, onProgress: (sent, total) {
        progress = total <= 0 ? 0 : sent / total;
        _updateProgress(key, progress);
      });
      _closeProgress(key);
      _snack('$name uploaded');
    } catch (e) {
      _closeProgress(key);
      _snack('Upload failed: ${api.errorMessage(e)}', error: true);
    }
  }

  final Map<String, BuildContext> _progressDialogs = {};
  final Map<String, ValueNotifier<double>> _progressValues = {};

  void _showProgress(String key, String title, double value) {
    if (_progressDialogs.containsKey(key)) return;
    final notifier = ValueNotifier(value);
    _progressValues[key] = notifier;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        _progressDialogs[key] = dialogContext;
        return AlertDialog(
          title: Text(title),
          content: ValueListenableBuilder<double>(
            valueListenable: notifier,
            builder: (_, v, __) => Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                LinearProgressIndicator(value: v == 0 ? null : v),
                const SizedBox(height: 10),
                Text(v == 0 ? 'Preparing…' : '${(v * 100).round()}%'),
              ],
            ),
          ),
        );
      },
    ).then((_) {
      _progressDialogs.remove(key);
      _progressValues.remove(key)?.dispose();
    });
  }

  void _updateProgress(String key, double value) => _progressValues[key]?.value = value;

  void _closeProgress(String key) {
    final c = _progressDialogs[key];
    if (c != null && c.mounted) Navigator.of(c).pop();
  }

  Future<void> _newText() async {
    final name = TextEditingController(text: 'notes.txt');
    final content = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('New text file'),
        content: SizedBox(
          width: 520,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: name, decoration: const InputDecoration(labelText: 'File name')),
            const SizedBox(height: 12),
            TextField(controller: content, maxLines: 7, decoration: const InputDecoration(labelText: 'Initial content')),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    if (result == true) {
      try {
        await api.createText(name.text.trim(), path, content.text);
        await refresh();
        _snack('Created ${name.text.trim()}');
      } catch (e) {
        _snack(api.errorMessage(e), error: true);
      }
    }
    name.dispose();
    content.dispose();
  }

  Future<void> _renameFolder(String folderName) async {
    final oldPrefix = _joinPath(path, folderName);
    final controller = TextEditingController(text: folderName);
    final value = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Rename folder'),
        content: TextField(controller: controller, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Rename')),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty || value == folderName) return;
    if (value == folderMarkerName || value.contains('/') || value.contains('\\')) {
      _snack('That is not a valid folder name.', error: true);
      return;
    }
    final newPrefix = _joinPath(path, value);
    final descendants = _filesUnder(oldPrefix);
    if (descendants.isEmpty) {
      _snack('Folder is empty and has no marker.', error: true);
      return;
    }
    try {
      for (final f in descendants) {
        final relativePath = f.path.substring(oldPrefix.length);
        await api.moveRename(f.id, '$newPrefix$relativePath', f.name);
      }
      await refresh();
      _snack('Folder renamed');
    } catch (e) {
      _snack('Could not rename folder: ${api.errorMessage(e)}', error: true);
      await refresh();
    }
  }

  Future<void> _moveFolder(String folderName) async {
    final oldPrefix = _joinPath(path, folderName);
    final controller = TextEditingController(text: path);
    final value = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Move folder'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Destination path', hintText: 'home/Projects/'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Move')),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty) return;
    final destinationParent = value.endsWith('/') ? value : '$value/';
    if (destinationParent == oldPrefix || destinationParent.startsWith(oldPrefix)) {
      _snack('A folder cannot be moved inside itself.', error: true);
      return;
    }
    final newPrefix = '$destinationParent$folderName/';
    final descendants = _filesUnder(oldPrefix);
    try {
      for (final f in descendants) {
        final relativePath = f.path.substring(oldPrefix.length);
        await api.moveRename(f.id, '$newPrefix$relativePath', f.name);
      }
      await refresh();
      _snack('Folder moved');
    } catch (e) {
      _snack('Could not move folder: ${api.errorMessage(e)}', error: true);
      await refresh();
    }
  }

  Future<void> _trashFolder(String folderName) async {
    final oldPrefix = _joinPath(path, folderName);
    final descendants = _filesUnder(oldPrefix);
    final yes = await _confirm(
      'Move folder to Trash?',
      'This will move ${descendants.length} item${descendants.length == 1 ? '' : 's'} inside “$folderName” to Trash.',
    );
    if (!yes) return;
    try {
      for (final f in descendants) {
        await api.trash(f.id);
      }
      await refresh();
      _snack('Folder moved to Trash');
    } catch (e) {
      _snack('Could not trash folder: ${api.errorMessage(e)}', error: true);
      await refresh();
    }
  }

  Future<void> _showFolderActions(String folderName) async {
    await showModalBottomSheet(
      context: context,
      backgroundColor: panel,
      showDragHandle: true,
      builder: (_) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.folder_open_rounded), title: const Text('Open'), onTap: () { Navigator.pop(context); _navigateTo(_joinPath(path, folderName)); }),
          ListTile(leading: const Icon(Icons.drive_file_rename_outline_rounded), title: const Text('Rename'), onTap: () { Navigator.pop(context); _renameFolder(folderName); }),
          ListTile(leading: const Icon(Icons.drive_file_move_rounded), title: const Text('Move'), onTap: () { Navigator.pop(context); _moveFolder(folderName); }),
          ListTile(leading: const Icon(Icons.delete_outline_rounded, color: red), title: const Text('Move to Trash'), onTap: () { Navigator.pop(context); _trashFolder(folderName); }),
        ]),
      ),
    );
  }

  Future<void> _rename(OvercastFile f) async {
    final controller = TextEditingController(text: f.name);
    final value = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Rename'),
        content: TextField(controller: controller, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Rename')),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty || value == f.name) return;
    try {
      await api.moveRename(f.id, f.path, value);
      await refresh();
      _snack('Renamed successfully');
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  Future<void> _move(OvercastFile f) async {
    final controller = TextEditingController(text: f.path);
    final value = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Move file'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Destination path', hintText: 'home/photos/'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Move')),
        ],
      ),
    );
    controller.dispose();
    if (value == null || value.isEmpty || value == f.path) return;
    try {
      await api.moveRename(f.id, value.endsWith('/') ? value : '$value/', f.name);
      await refresh();
      _snack('Moved successfully');
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  Future<void> _trash(OvercastFile f) async {
    final yes = await _confirm('Move to Trash?', '“${f.name}” will be moved to Trash.');
    if (!yes) return;
    try {
      await api.trash(f.id);
      await refresh();
      _snack('Moved to Trash');
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  Future<void> _restore(TrashEntry f) async {
    try {
      await api.restore(f.id);
      await refresh();
      _snack('Restored ${f.name}');
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  Future<void> _permanentDelete(TrashEntry f) async {
    final yes = await _confirm('Delete permanently?', 'This cannot be undone.');
    if (!yes) return;
    try {
      await api.permanentlyDelete(f.id);
      await refresh();
      _snack('Permanently deleted');
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  Future<bool> _confirm(String title, String body) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: Text(title),
            content: Text(body),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Continue')),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _download(OvercastFile f) async {
    Directory? dir;
    if (!Platform.isAndroid && !Platform.isIOS) dir = await getDownloadsDirectory();
    dir ??= await getApplicationDocumentsDirectory();
    final safe = _uniqueName(dir, f.name);
    final progressKey = 'download:${f.id}';
    _showProgress(progressKey, 'Downloading ${f.name}', 0);
    try {
      await api.downloadToPath(f.id, safe, onProgress: (done, total) {
        _updateProgress(progressKey, total <= 0 ? 0 : done / total);
      });
      _closeProgress(progressKey);
      _snack('Downloaded to $safe');
      await _openPath(safe);
    } catch (e) {
      _closeProgress(progressKey);
      _snack('Download failed: ${api.errorMessage(e)}', error: true);
    }
  }

  String _uniqueName(Directory dir, String name) {
    final first = File('${dir.path}${Platform.pathSeparator}$name');
    if (!first.existsSync()) return first.path;
    final dot = name.lastIndexOf('.');
    final stem = dot > 0 ? name.substring(0, dot) : name;
    final ext = dot > 0 ? name.substring(dot) : '';
    for (var i = 1; i < 10000; i++) {
      final f = File('${dir.path}${Platform.pathSeparator}$stem ($i)$ext');
      if (!f.existsSync()) return f.path;
    }
    return first.path;
  }

  Future<void> _openPath(String path) async {
    final uri = Uri.file(path);
    await launchUrl(uri);
  }


  Future<void> _open(OvercastFile f) async {
    if (f.isText) {
      await _textEditor(f);
    } else if (f.isImage || f.isVideo || f.isAudio) {
      await showDialog(context: context, builder: (_) => PreviewDialog(api: api, file: f));
    } else if (f.isPdf) {
      await launchUrl(Uri.parse(api.previewUrl(f.id)));
    } else {
      await _download(f);
    }
  }

  Future<void> _textEditor(OvercastFile f) async {
    try {
      final initial = await api.readText(f.id);
      if (!mounted) return;
      await Navigator.push(context, MaterialPageRoute(builder: (_) => TextEditorPage(api: api, file: f, initial: initial)));
      await refresh();
    } catch (e) {
      _snack(api.errorMessage(e), error: true);
    }
  }

  void _snack(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? const Color(0xFF5A1E2B) : panel2,
      behavior: SnackBarBehavior.floating,
    ));
  }

  void _navigateTo(String p) {
    setState(() {
      path = p.endsWith('/') ? p : '$p/';
      section = 'Home';
    });
    refresh();
  }

  List<String> _crumbs() {
    final clean = path.replaceFirst(RegExp(r'/$'), '');
    return clean.split('/').where((e) => e.isNotEmpty).toList();
  }

  Future<void> _showActions(OvercastFile f) async {
    await showModalBottomSheet(
      context: context,
      backgroundColor: panel,
      showDragHandle: true,
      builder: (_) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.open_in_new_rounded), title: const Text('Open'), onTap: () { Navigator.pop(context); _open(f); }),
          ListTile(leading: const Icon(Icons.download_rounded), title: const Text('Download'), onTap: () { Navigator.pop(context); _download(f); }),
          ListTile(leading: const Icon(Icons.drive_file_rename_outline_rounded), title: const Text('Rename'), onTap: () { Navigator.pop(context); _rename(f); }),
          ListTile(leading: const Icon(Icons.drive_file_move_rounded), title: const Text('Move'), onTap: () { Navigator.pop(context); _move(f); }),
          ListTile(leading: const Icon(Icons.delete_outline_rounded, color: red), title: const Text('Move to Trash'), onTap: () { Navigator.pop(context); _trash(f); }),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: LayoutBuilder(builder: (_, c) {
            final desktop = c.maxWidth >= 900;
            return Row(children: [
              if (desktop) _sidebar(),
              Expanded(child: _body(desktop)),
            ]);
          }),
        ),
      );

  Widget _sidebar() => Container(
        width: 255,
        margin: const EdgeInsets.all(14),
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 16),
        decoration: BoxDecoration(color: const Color(0xFF091020), borderRadius: BorderRadius.circular(24), border: Border.all(color: border)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(width: 44, height: 44, decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), gradient: const LinearGradient(colors: [accent, purple])), child: const Icon(Icons.cloud_rounded, color: Colors.white)),
            const SizedBox(width: 12),
            const Text('OVERCAST', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, letterSpacing: 1.5)),
          ]),
          const SizedBox(height: 28),
          _nav(Icons.home_rounded, 'Home'),
          _nav(Icons.delete_outline_rounded, 'Trash'),
          const SizedBox(height: 14),
          const Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('STORAGE', style: TextStyle(fontSize: 11, letterSpacing: 1.3, color: Colors.white38))),
          const SizedBox(height: 10),
          if (storage != null) _storageCard(),
          const Spacer(),
          Container(padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: panel, borderRadius: BorderRadius.circular(16), border: Border.all(color: border)), child: Row(children: [
            Icon(connected ? Icons.cloud_done_rounded : Icons.cloud_off_rounded, size: 18, color: connected ? green : red),
            const SizedBox(width: 9),
            Expanded(child: Text(connected ? 'Connected to Overcast' : 'Not connected to Overcast', style: const TextStyle(fontSize: 12))),
          ])),
          const SizedBox(height: 8),
          ListTile(leading: const Icon(Icons.settings_outlined), title: const Text('Settings'), dense: true, onTap: _settings),
        ]),
      );

  Widget _storageCard() {
    final s = storage!;
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${_bytes(s.used)} used', style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 9),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              minHeight: 7,
              value: s.fraction,
              backgroundColor: Colors.white10,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${_bytes(s.free)} free of ${_bytes(s.total)}',
            style: const TextStyle(fontSize: 11, color: Colors.white54),
          ),
        ],
      ),
    );
  }

  Widget _nav(IconData icon, String label) {
    final active = section == label;
    return Padding(padding: const EdgeInsets.only(bottom: 5), child: ListTile(
      dense: true, selected: active, selectedTileColor: const Color(0x187AA2F7), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      leading: Icon(icon, size: 20), title: Text(label), onTap: () {
        setState(() { section = label; if (label == 'Home') path = 'home/'; });
        refresh();
      },
    ));
  }

  Widget _body(bool desktop) => Padding(padding: EdgeInsets.fromLTRB(desktop ? 8 : 14, 14, 14, 14), child: Column(children: [
    _topbar(),
    if (!desktop) _mobileNav(),
    const SizedBox(height: 18),
    Expanded(child: _content()),
  ]));

  Widget _topbar() => Row(children: [
    Expanded(
      child: TextField(
        controller: search,
        onChanged: (v) => setState(() => query = v),
        decoration: InputDecoration(
          hintText: 'Search your Overcast',
          prefixIcon: const Icon(Icons.search_rounded),
          suffixIcon: query.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () {
                    search.clear();
                    setState(() => query = '');
                  },
                ),
        ),
      ),
    ),
    const SizedBox(width: 9),
    IconButton.filledTonal(onPressed: refresh, tooltip: 'Refresh', icon: const Icon(Icons.refresh_rounded)),
    const SizedBox(width: 5),
    IconButton.filledTonal(onPressed: _settings, tooltip: 'Settings', icon: const Icon(Icons.settings_outlined)),
  ]);

  Widget _mobileNav() => Padding(padding: const EdgeInsets.only(top: 10), child: Row(children: [
    Expanded(child: _mobileButton(Icons.home_rounded, 'Home')),
    const SizedBox(width: 8),
    Expanded(child: _mobileButton(Icons.delete_outline_rounded, 'Trash')),
  ]));

  Widget _mobileButton(IconData icon, String label) => OutlinedButton.icon(onPressed: () { setState(() { section = label; if (label == 'Home') path = 'home/'; }); refresh(); }, icon: Icon(icon), label: Text(label));

  Widget _content() {
    if (loading) return const Center(child: CircularProgressIndicator());
    if (!connected) return _offline();
    if (section == 'Trash') return _trashView();
    return _homeView();
  }

  Widget _homeView() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(children: [Expanded(child: _breadcrumbs()), PopupMenuButton<String>(onSelected: (v) { if (v == 'file') _pickUploads(); if (v == 'folder') _pickFolderUpload(); if (v == 'text') _newText(); if (v == 'newfolder') _createFolder(); }, itemBuilder: (_) => const [PopupMenuItem(value: 'file', child: ListTile(leading: Icon(Icons.upload_file_rounded), title: Text('Upload files'))), PopupMenuItem(value: 'folder', child: ListTile(leading: Icon(Icons.drive_folder_upload_rounded), title: Text('Upload folder'))), PopupMenuItem(value: 'newfolder', child: ListTile(leading: Icon(Icons.create_new_folder_rounded), title: Text('New folder'))), PopupMenuItem(value: 'text', child: ListTile(leading: Icon(Icons.note_add_outlined), title: Text('New text file')))], child: FilledButton.icon(onPressed: null, icon: const Icon(Icons.add_rounded), label: const Text('New')))]),
    const SizedBox(height: 18),
    Row(children: [Text('${filtered.length} item${filtered.length == 1 ? '' : 's'}', style: const TextStyle(color: Colors.white54)), const Spacer(), IconButton(onPressed: () { setState(() => grid = true); prefs?.setBool('grid', true); }, icon: Icon(Icons.grid_view_rounded, color: grid ? accent : Colors.white54)), IconButton(onPressed: () { setState(() => grid = false); prefs?.setBool('grid', false); }, icon: Icon(Icons.view_list_rounded, color: !grid ? accent : Colors.white54))]),
    const SizedBox(height: 8),
    Expanded(child: _itemsView(filtered)),
  ]);

  Widget _breadcrumbs() {
    final crumbs = _crumbs();
    return SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: [
      TextButton(onPressed: () => _navigateTo('home/'), child: const Text('Home')),
      for (var i = 1; i < crumbs.length; i++) ...[
        const Icon(Icons.chevron_right_rounded, size: 18, color: Colors.white38),
        TextButton(onPressed: () => _navigateTo('${crumbs.take(i + 1).join('/')}/'), child: Text(crumbs[i])),
      ],
    ]));
  }

  Widget _itemsView(List<OvercastFile> data) {
    final folders = childFolders;
    if (data.isEmpty && folders.isEmpty) return _empty();

    if (!grid) {
      return ListView.separated(
        itemCount: folders.length + data.length,
        separatorBuilder: (_, __) => const SizedBox(height: 7),
        itemBuilder: (_, i) {
          if (i < folders.length) return _folderListCard(folders[i]);
          return _listCard(data[i - folders.length]);
        },
      );
    }

    return GridView.builder(
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 230,
        mainAxisExtent: 178,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: folders.length + data.length,
      itemBuilder: (_, i) {
        if (i < folders.length) return _folderGridCard(folders[i]);
        return _gridCard(data[i - folders.length]);
      },
    );
  }

  Widget _folderGridCard(String name) {
    return Card(
      color: panel,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onDoubleTap: () => _navigateTo('$path$name/'),
        onLongPress: () => _showFolderActions(name),
        child: Padding(
          padding: const EdgeInsets.all(15),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(
                child: Center(
                  child: Icon(Icons.folder_rounded, size: 62, color: accent),
                ),
              ),
              Row(children: [Expanded(child: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700))), IconButton(onPressed: () => _showFolderActions(name), icon: const Icon(Icons.more_horiz_rounded, size: 19), padding: EdgeInsets.zero, constraints: const BoxConstraints())]),
              const Text('Folder', style: TextStyle(fontSize: 11, color: Colors.white54)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _folderListCard(String name) {
    return Card(
      color: panel,
      child: ListTile(
        onTap: () => _navigateTo('$path$name/'),
        leading: const Icon(Icons.folder_rounded, color: accent, size: 32),
        title: Text(name, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: const Text('Folder', style: TextStyle(color: Colors.white54)),
        trailing: IconButton(onPressed: () => _showFolderActions(name), icon: const Icon(Icons.more_horiz_rounded)),
      ),
    );
  }

  Widget _gridCard(OvercastFile f) {
    return Card(
      color: panel,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onDoubleTap: () => _open(f),
        onLongPress: () => _showActions(f),
        child: Padding(
          padding: const EdgeInsets.all(15),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: Center(child: _fileIcon(f, 55))),
              Row(
                children: [
                  Expanded(child: Text(f.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700))),
                  IconButton(
                    onPressed: () => _showActions(f),
                    icon: const Icon(Icons.more_horiz_rounded, size: 19),
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),
              Text('${_bytes(f.size)} • ${f.extension.toUpperCase()}', style: const TextStyle(fontSize: 11, color: Colors.white54)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _listCard(OvercastFile f) {
    return Card(
      color: panel,
      child: ListTile(
        onTap: () => _open(f),
        onLongPress: () => _showActions(f),
        leading: _fileIcon(f, 31),
        title: Text(f.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text('${_bytes(f.size)} • ${f.lastEdited ?? ''}', style: const TextStyle(color: Colors.white54)),
        trailing: PopupMenuButton<String>(
          onSelected: (v) {
            if (v == 'download') {
              _download(f);
            } else if (v == 'rename') {
              _rename(f);
            } else if (v == 'move') {
              _move(f);
            } else if (v == 'trash') {
              _trash(f);
            }
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'download', child: Text('Download')),
            PopupMenuItem(value: 'rename', child: Text('Rename')),
            PopupMenuItem(value: 'move', child: Text('Move')),
            PopupMenuItem(value: 'trash', child: Text('Move to Trash')),
          ],
        ),
      ),
    );
  }

  Widget _fileIcon(OvercastFile f, double size) {
    final color = f.isImage ? const Color(0xFF69C5FF) : f.isVideo ? const Color(0xFFC49BFF) : f.isAudio ? const Color(0xFFFFB86B) : f.isText ? const Color(0xFF78D7A5) : f.isPdf ? red : accent;
    final icon = f.isImage ? Icons.image_rounded : f.isVideo ? Icons.movie_rounded : f.isAudio ? Icons.audio_file_rounded : f.isText ? Icons.description_rounded : f.isPdf ? Icons.picture_as_pdf_rounded : Icons.insert_drive_file_rounded;
    return Container(width: size + 24, height: size + 24, decoration: BoxDecoration(color: color.withValues(alpha: .10), borderRadius: BorderRadius.circular(18)), child: Icon(icon, size: size, color: color));
  }

  Widget _trashView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Trash', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
        const SizedBox(height: 5),
        Text('${trash.length} item${trash.length == 1 ? '' : 's'}', style: const TextStyle(color: Colors.white54)),
        const SizedBox(height: 18),
        Expanded(
          child: trash.isEmpty
              ? _empty(trash: true)
              : ListView.separated(
                  itemCount: trash.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 7),
                  itemBuilder: (_, i) {
                    final f = trash[i];
                    return Card(
                      color: panel,
                      child: ListTile(
                        leading: _fileIcon(f, 30),
                        title: Text(f.name),
                        subtitle: Text('Originally in ${f.lastLocation}', style: const TextStyle(color: Colors.white54)),
                        trailing: Wrap(
                          children: [
                            IconButton(tooltip: 'Restore', onPressed: () => _restore(f), icon: const Icon(Icons.restore_rounded, color: green)),
                            IconButton(tooltip: 'Delete permanently', onPressed: () => _permanentDelete(f), icon: const Icon(Icons.delete_forever_rounded, color: red)),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _empty({bool trash = false}) => Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(trash ? Icons.delete_sweep_rounded : Icons.cloud_queue_rounded, size: 76, color: Colors.white12), const SizedBox(height: 16), Text(trash ? 'Trash is empty' : 'Nothing here yet', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)), const SizedBox(height: 7), Text(trash ? 'Deleted files will appear here.' : 'Upload something to get started.', style: const TextStyle(color: Colors.white54))]));

  Widget _offline() => Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.cloud_off_rounded, size: 82, color: Colors.white12), const SizedBox(height: 18), const Text('Not connected to Overcast', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)), const SizedBox(height: 7), Text(server, style: const TextStyle(color: Colors.white38)), const SizedBox(height: 20), OutlinedButton.icon(onPressed: refresh, icon: const Icon(Icons.refresh_rounded), label: const Text('Try again'))]));

  String _bytes(int n) {
    if (n < 1024) return '$n B';
    if (n < 1024 * 1024) return '${(n / 1024).toStringAsFixed(1)} KB';
    if (n < 1024 * 1024 * 1024) return '${(n / 1048576).toStringAsFixed(1)} MB';
    return '${(n / 1073741824).toStringAsFixed(2)} GB';
  }
}

class TextEditorPage extends StatefulWidget {
  final OvercastApi api;
  final OvercastFile file;
  final String initial;
  const TextEditorPage({super.key, required this.api, required this.file, required this.initial});
  @override State<TextEditorPage> createState() => _TextEditorPageState();
}
class _TextEditorPageState extends State<TextEditorPage> {
  late final TextEditingController controller = TextEditingController(text: widget.initial);
  bool saving = false;
  bool dirty = false;
  @override void dispose() { controller.dispose(); super.dispose(); }
  Future<void> save() async {
    setState(() => saving = true);
    try { await widget.api.saveText(widget.file.id, controller.text); if (mounted) setState(() { saving = false; dirty = false; }); }
    catch (e) { if (mounted) { setState(() => saving = false); ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(widget.api.errorMessage(e)))); } }
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: Text(widget.file.name), actions: [if (dirty) const Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Center(child: Text('Unsaved', style: TextStyle(color: Colors.orange)))), IconButton(onPressed: saving ? null : save, icon: saving ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_rounded))]), body: Padding(padding: const EdgeInsets.all(18), child: TextField(controller: controller, expands: true, maxLines: null, minLines: null, onChanged: (_) => setState(() => dirty = true), textAlignVertical: TextAlignVertical.top, style: const TextStyle(fontFamily: 'monospace', fontSize: 14), decoration: const InputDecoration(hintText: 'Start typing…'))));
}

class PreviewDialog extends StatefulWidget {
  final OvercastApi api;
  final OvercastFile file;
  const PreviewDialog({super.key, required this.api, required this.file});
  @override State<PreviewDialog> createState() => _PreviewDialogState();
}
class _PreviewDialogState extends State<PreviewDialog> {
  VideoPlayerController? video;
  AudioPlayer? audio;
  bool audioPlaying = false;
  String? error;
  @override void initState() { super.initState(); _init(); }
  Future<void> _init() async {
    try {
      if (widget.file.isVideo) {
        final v = VideoPlayerController.networkUrl(Uri.parse(widget.api.streamUrl(widget.file.id)));
        await v.initialize(); await v.play(); if (mounted) setState(() => video = v);
      } else if (widget.file.isAudio) {
        final a = AudioPlayer(); await a.play(UrlSource(widget.api.streamUrl(widget.file.id))); if (mounted) setState(() { audio = a; audioPlaying = true; });
      }
    } catch (e) { if (mounted) setState(() => error = widget.api.errorMessage(e)); }
  }
  @override void dispose() { video?.dispose(); audio?.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => Dialog(backgroundColor: panel, insetPadding: const EdgeInsets.all(22), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1000, maxHeight: 760), child: Padding(padding: const EdgeInsets.all(14), child: Column(children: [Row(children: [Expanded(child: Text(widget.file.name, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18))), IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded))]), const SizedBox(height: 8), Expanded(child: _body())]))));
  Widget _body() {
    if (error != null) return Center(child: Text(error!));
    if (widget.file.isImage) return InteractiveViewer(child: Image.network(widget.api.previewUrl(widget.file.id), fit: BoxFit.contain, errorBuilder: (_, __, ___) => const Center(child: Text('Preview unavailable'))));
    if (widget.file.isVideo) { final v = video; if (v == null || !v.value.isInitialized) return const Center(child: CircularProgressIndicator()); return Column(children: [Expanded(child: Center(child: AspectRatio(aspectRatio: v.value.aspectRatio, child: VideoPlayer(v)))), VideoProgressIndicator(v, allowScrubbing: true), Row(mainAxisAlignment: MainAxisAlignment.center, children: [IconButton(onPressed: () => setState(() { v.value.isPlaying ? v.pause() : v.play(); }), icon: Icon(v.value.isPlaying ? Icons.pause_circle_filled : Icons.play_circle_fill, size: 42))])]); }
    if (widget.file.isAudio) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.audio_file_rounded, size: 100, color: accent), const SizedBox(height: 16), Text(widget.file.name, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 16), IconButton(onPressed: () async { if (audio == null) return; if (audioPlaying) { await audio!.pause(); } else { await audio!.resume(); } setState(() => audioPlaying = !audioPlaying); }, icon: Icon(audioPlaying ? Icons.pause_circle_filled : Icons.play_circle_fill, size: 58))]));
    return const Center(child: Text('No preview available.'));
  }
}
