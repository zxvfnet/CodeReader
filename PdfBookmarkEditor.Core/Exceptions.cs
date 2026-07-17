namespace PdfBookmarkEditor.Core;

/// <summary>本アプリのしおり操作で発生する例外の基底。</summary>
public class PdfBookmarkException : Exception
{
    public PdfBookmarkException(string message) : base(message) { }
    public PdfBookmarkException(string message, Exception inner) : base(message, inner) { }
}

/// <summary>パスワード付き(暗号化)PDFを開こうとした。</summary>
public class PdfEncryptedException : PdfBookmarkException
{
    public PdfEncryptedException(string path, Exception inner)
        : base($"パスワード付きPDFは開けません: {path}", inner) { }
}

/// <summary>PDFの読み込みに失敗した(破損・非PDFなど)。</summary>
public class PdfLoadException : PdfBookmarkException
{
    public PdfLoadException(string path, Exception inner)
        : base($"PDFを読み込めません: {path} ({inner.Message})", inner) { }
}

/// <summary>PDFの保存に失敗した。</summary>
public class PdfSaveException : PdfBookmarkException
{
    public PdfSaveException(string path, Exception inner)
        : base($"PDFを保存できません: {path} ({inner.Message})", inner) { }
}

/// <summary>しおりデータの検証エラー。Errors に個別メッセージを保持する。</summary>
public class BookmarkValidationException : PdfBookmarkException
{
    public IReadOnlyList<string> Errors { get; }

    public BookmarkValidationException(IReadOnlyList<string> errors)
        : base("しおりデータに誤りがあります:\n" + string.Join("\n", errors))
    {
        Errors = errors;
    }
}

/// <summary>JSONの読み取り・形式エラー。</summary>
public class BookmarkJsonException : PdfBookmarkException
{
    public BookmarkJsonException(string message) : base(message) { }
    public BookmarkJsonException(string message, Exception inner) : base(message, inner) { }
}
