"""Test HTML to PDF parsing, especially nested lists."""
import sys
sys.path.insert(0, '.')

from main import html_to_flowables
from reportlab.lib.styles import getSampleStyleSheet

def test_nested_bullet_list():
    """Test that nested bullet lists are parsed correctly."""
    html = """
    <ul>
        <li>bullet
            <ul>
                <li>bullet down</li>
                <li>bullown2</li>
            </ul>
        </li>
        <li>nex tlbt</li>
    </ul>
    """

    styles = getSampleStyleSheet()
    flowables = html_to_flowables(html, styles)

    # Should have multiple flowables (paragraphs + spacers)
    assert len(flowables) > 0, "Should produce flowables"

    # Extract text from paragraphs
    texts = []
    for f in flowables:
        if hasattr(f, 'text'):
            # Strip bullet character and whitespace
            text = f.text.replace('\u2022', '').strip()
            if text:
                texts.append(text)

    print(f"Extracted texts: {texts}")

    # Check all items are present and separate
    assert any('bullet' in t and 'down' not in t for t in texts), "Should have 'bullet' as separate item"
    assert any('bullet down' in t for t in texts), "Should have 'bullet down'"
    assert any('bullown2' in t for t in texts), "Should have 'bullown2'"
    assert any('nex tlbt' in t for t in texts), "Should have 'nex tlbt'"

    print("All nested list tests passed!")

def test_simple_list():
    """Test simple bullet list."""
    html = "<ul><li>item 1</li><li>item 2</li></ul>"

    styles = getSampleStyleSheet()
    flowables = html_to_flowables(html, styles)

    assert len(flowables) > 0, "Should produce flowables"
    print("Simple list test passed!")

def test_numbered_list():
    """Test numbered list."""
    html = "<ol><li>first</li><li>second</li></ol>"

    styles = getSampleStyleSheet()
    flowables = html_to_flowables(html, styles)

    texts = [f.text for f in flowables if hasattr(f, 'text')]
    print(f"Numbered list texts: {texts}")

    assert any('1.' in t for t in texts), "Should have numbered items"
    print("Numbered list test passed!")

if __name__ == '__main__':
    test_simple_list()
    test_numbered_list()
    test_nested_bullet_list()
    print("\nAll tests passed!")
