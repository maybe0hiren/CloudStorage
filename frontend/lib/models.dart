class OvercastFile {
  final String id;
  final String name;
  final String path;
  final String format;
  final int size;
  final String? lastEdited;
  final String? createdAt;
  final String? link;
  final String? sha256;

  const OvercastFile({
    required this.id,
    required this.name,
    required this.path,
    required this.format,
    required this.size,
    this.lastEdited,
    this.createdAt,
    this.link,
    this.sha256,
  });

  String get extension => format.toLowerCase().replaceFirst('.', '');

  bool get isImage => const {
        'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'
      }.contains(extension);

  bool get isVideo => const {
        'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v',
        'mpeg', 'mpg', '3gp'
      }.contains(extension);

  bool get isAudio => const {
        'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac', 'opus'
      }.contains(extension);

  bool get isText => const {
        'txt', 'md', 'json', 'xml', 'csv', 'log', 'py', 'js', 'ts',
        'jsx', 'tsx', 'html', 'css', 'scss', 'c', 'cpp', 'h', 'hpp',
        'java', 'kt', 'rs', 'go', 'php', 'rb', 'sh', 'yml', 'yaml'
      }.contains(extension);

  bool get isPdf => extension == 'pdf';

  factory OvercastFile.fromJson(Map<String, dynamic> json) {
    return OvercastFile(
      id: '${json['UniqueID'] ?? ''}',
      name: '${json['FileName'] ?? 'Unnamed'}',
      path: '${json['FilePath'] ?? 'home/'}',
      format: '${json['Format'] ?? 'bin'}',
      size: (json['Size'] as num?)?.toInt() ?? 0,
      lastEdited: json['LastEdited']?.toString(),
      createdAt: json['CreatedAt']?.toString(),
      link: json['Link']?.toString(),
      sha256: json['SHA256']?.toString(),
    );
  }
}

class StorageInfo {
  final int total;
  final int used;
  final int free;

  const StorageInfo({required this.total, required this.used, required this.free});

  double get fraction => total <= 0 ? 0 : used / total;

  factory StorageInfo.fromJson(Map<String, dynamic> json) => StorageInfo(
        total: (json['total'] as num?)?.toInt() ?? 0,
        used: (json['used'] as num?)?.toInt() ?? 0,
        free: (json['free'] as num?)?.toInt() ?? 0,
      );
}

class TrashEntry extends OvercastFile {
  final String lastLocation;
  final String trashedDate;

  const TrashEntry({
    required super.id,
    required super.name,
    required super.path,
    required super.format,
    required super.size,
    super.lastEdited,
    super.createdAt,
    super.link,
    super.sha256,
    required this.lastLocation,
    required this.trashedDate,
  });

  factory TrashEntry.fromJson(Map<String, dynamic> json) => TrashEntry(
        id: '${json['UniqueID'] ?? json['UID'] ?? ''}',
        name: '${json['FileName'] ?? 'Unnamed'}',
        path: '${json['FilePath'] ?? 'Trash/'}',
        format: '${json['Format'] ?? 'bin'}',
        size: (json['Size'] as num?)?.toInt() ?? 0,
        lastEdited: json['LastEdited']?.toString(),
        createdAt: json['CreatedAt']?.toString(),
        link: json['Link']?.toString(),
        sha256: json['SHA256']?.toString(),
        lastLocation: '${json['LastLoc'] ?? 'home/'}',
        trashedDate: '${json['TrashedDate'] ?? ''}',
      );
}
