import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'models.dart';

class OvercastApi {
  final Dio dio;

  OvercastApi(String baseUrl)
      : dio = Dio(BaseOptions(
          baseUrl: baseUrl.trim().replaceFirst(RegExp(r'/*$'), ''),
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(minutes: 5),
          sendTimeout: const Duration(minutes: 30),
          headers: const {'Accept': 'application/json'},
        ));

  dynamic _json(Response response) => response.data is String
      ? jsonDecode(response.data as String)
      : response.data;

  String errorMessage(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['error'] != null) return '${data['error']}';
      if (data is String && data.isNotEmpty) return data;
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.connectionError) {
        return 'Overcast is unreachable on this network.';
      }
      return error.message ?? 'Network error';
    }
    return error.toString();
  }

  Future<bool> isHealthy() async {
    final response = await dio.get('/api/health');
    final data = Map<String, dynamic>.from(_json(response) as Map);
    return data['status'] == 'ok' && data['database'] == true && data['storage'] == true;
  }

  Future<StorageInfo> storage() async {
    final response = await dio.get('/api/storage');
    return StorageInfo.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<List<OvercastFile>> files([String? path]) async {
    final response = await dio.get(
      '/api/files',
      queryParameters: path == null ? null : {'path': path},
    );
    final data = _json(response) as List;
    return data.map((e) => OvercastFile.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<OvercastFile> file(String id) async {
    final response = await dio.get('/api/files/$id');
    return OvercastFile.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<OvercastFile> upload(
    String path,
    String filePath, {
    void Function(int sent, int total)? onProgress,
  }) async {
    final name = filePath.split(RegExp(r'[/\\]')).last;
    final form = FormData.fromMap({
      'path': path,
      'encryption': 'none',
      'file': await MultipartFile.fromFile(filePath, filename: name),
    });
    final response = await dio.post(
      '/api/files/upload',
      data: form,
      onSendProgress: onProgress,
    );
    return OvercastFile.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<OvercastFile> createText(String name, String path, String content) async {
    return uploadBytes(
      path,
      name,
      Uint8List.fromList(utf8.encode(content)),
    );
  }

  Future<OvercastFile> uploadBytes(
    String path,
    String name,
    Uint8List bytes, {
    void Function(int sent, int total)? onProgress,
  }) async {
    final form = FormData.fromMap({
      'path': path,
      'encryption': 'none',
      'file': MultipartFile.fromBytes(bytes, filename: name),
    });
    final response = await dio.post(
      '/api/files/upload',
      data: form,
      onSendProgress: onProgress,
    );
    return OvercastFile.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<String> downloadToPath(String id, String outputPath,
      {void Function(int, int)? onProgress}) async {
    await dio.download('/api/files/$id/download', outputPath, onReceiveProgress: onProgress);
    return outputPath;
  }

  String previewUrl(String id) => '${dio.options.baseUrl}/api/files/$id/preview';
  String streamUrl(String id) => '${dio.options.baseUrl}/api/files/$id/stream';
  String downloadUrl(String id) => '${dio.options.baseUrl}/api/files/$id/download';

  Future<String> readText(String id) async {
    final response = await dio.get('/api/files/$id/text');
    final data = Map<String, dynamic>.from(_json(response) as Map);
    return '${data['content'] ?? ''}';
  }

  Future<OvercastFile> saveText(String id, String content) async {
    final response = await dio.put('/api/files/$id/text', data: {'content': content});
    return OvercastFile.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<OvercastFile> moveRename(String id, String newPath, String newName) async {
    final response = await dio.put('/api/files/$id/path', data: {
      'newPath': newPath,
      'newName': newName,
    });
    return OvercastFile.fromJson(Map<String, dynamic>.from(_json(response) as Map));
  }

  Future<void> trash(String id) async => dio.delete('/api/files/$id');

  Future<List<TrashEntry>> trashList() async {
    final response = await dio.get('/api/trash');
    final data = _json(response) as List;
    return data.map((e) => TrashEntry.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  Future<void> restore(String id) async => dio.post('/api/trash/$id/restore');

  Future<void> permanentlyDelete(String id) async => dio.delete('/api/trash/$id');


  Future<Uint8List> fetchBytes(String id) async {
    final response = await dio.get<List<int>>(
      '/api/files/$id/preview',
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(response.data ?? <int>[]);
  }
}
