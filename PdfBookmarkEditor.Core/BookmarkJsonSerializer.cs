using System.Text.Json;
using System.Text.Json.Serialization;

namespace PdfBookmarkEditor.Core;

/// <summary>
/// しおり階層のJSONエクスポート/インポート。
/// 形式は "PdfBookmarkEditor/1"(詳細仕様 2.5 参照)。
/// </summary>
public static class BookmarkJsonSerializer
{
    public const string FormatId = "PdfBookmarkEditor/1";

    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    private class FileDto
    {
        [JsonPropertyName("format")]
        public string? Format { get; set; }

        [JsonPropertyName("bookmarks")]
        public List<NodeDto>? Bookmarks { get; set; }
    }

    private class NodeDto
    {
        [JsonPropertyName("title")]
        public string? Title { get; set; }

        [JsonPropertyName("page")]
        public int? Page { get; set; }

        [JsonPropertyName("bold")]
        public bool Bold { get; set; }

        [JsonPropertyName("italic")]
        public bool Italic { get; set; }

        [JsonPropertyName("expanded")]
        public bool Expanded { get; set; }

        [JsonPropertyName("children")]
        public List<NodeDto>? Children { get; set; }
    }

    /// <summary>ツリー全体をJSON文字列へ書き出す。</summary>
    public static string Export(IEnumerable<BookmarkNode> bookmarks)
    {
        var dto = new FileDto
        {
            Format = FormatId,
            Bookmarks = bookmarks.Select(ToDto).ToList(),
        };
        return JsonSerializer.Serialize(dto, Options);
    }

    /// <summary>
    /// JSON文字列からツリーを復元する。pageCount を指定するとページ範囲も検証する。
    /// </summary>
    /// <exception cref="BookmarkJsonException">構文エラー・形式不一致の場合。</exception>
    /// <exception cref="BookmarkValidationException">タイトル欠落・ページ範囲外の場合。</exception>
    public static List<BookmarkNode> Import(string json, int? pageCount = null)
    {
        FileDto? dto;
        try
        {
            dto = JsonSerializer.Deserialize<FileDto>(json, Options);
        }
        catch (JsonException e)
        {
            throw new BookmarkJsonException(
                $"JSONの構文エラーです(行 {e.LineNumber + 1} 付近): {e.Message}", e);
        }

        if (dto == null)
        {
            throw new BookmarkJsonException("JSONの内容が空です。");
        }
        if (dto.Format != FormatId)
        {
            throw new BookmarkJsonException(
                $"形式が不一致です。format には \"{FormatId}\" を指定してください(実際: \"{dto.Format}\")。");
        }

        var errors = new List<string>();
        var nodes = (dto.Bookmarks ?? new List<NodeDto>())
            .Select((n, i) => FromDto(n, pageCount, $"{i + 1}", errors))
            .ToList();
        if (errors.Count > 0)
        {
            throw new BookmarkValidationException(errors);
        }
        return nodes;
    }

    private static NodeDto ToDto(BookmarkNode node)
    {
        return new NodeDto
        {
            Title = node.Title,
            Page = node.Page,
            Bold = node.Bold,
            Italic = node.Italic,
            Expanded = node.Expanded,
            Children = node.Children.Count > 0 ? node.Children.Select(ToDto).ToList() : null,
        };
    }

    private static BookmarkNode FromDto(NodeDto dto, int? pageCount, string path, List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(dto.Title))
        {
            errors.Add($"しおり {path}: title は必須です。");
        }
        if (dto.Page is int page)
        {
            if (page < 1)
            {
                errors.Add($"しおり {path} 「{dto.Title}」: page は1以上にしてください(実際: {page})。");
            }
            else if (pageCount is int max && page > max)
            {
                errors.Add($"しおり {path} 「{dto.Title}」: page {page} は範囲外です(1〜{max})。");
            }
        }

        var node = new BookmarkNode
        {
            Title = dto.Title ?? "",
            Page = dto.Page,
            Bold = dto.Bold,
            Italic = dto.Italic,
            Expanded = dto.Expanded,
        };
        var children = dto.Children ?? new List<NodeDto>();
        for (int i = 0; i < children.Count; i++)
        {
            node.Children.Add(FromDto(children[i], pageCount, $"{path}-{i + 1}", errors));
        }
        return node;
    }
}
