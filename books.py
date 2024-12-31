"Markdown book texts in files and directories."

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile

import yaml

import auth
import constants
from errors import *
import markdown
import users
import utils
from utils import Tx


FRONTMATTER = re.compile(r"^---([\n\r].*?[\n\r])---[\n\r](.*)$", re.DOTALL)


# Book instances in-memory database. Key: id; value: Book instance.
_books = {}

# References book in-memory.
_refs = None


def read_books():
    "Read in all books into memory, including '_refs'."
    global _refs
    refspath = Path(os.environ["WRITETHATBOOK_DIR"]) / constants.REFS
    # Create the references directory, if it doesn't exist.
    if not refspath.exists():
        refspath.mkdir()
        with open(refspath / "index.md", "w") as outfile:
            outfile.write("---\n")
            outfile.write(yaml.dump({"title": "References"}))
            outfile.write(yaml.dump({"owner": constants.SYSTEM_USERID}))
            outfile.write("---\n")
    _refs = Book(refspath)

    global _books
    _books.clear()
    for bookpath in Path(os.environ["WRITETHATBOOK_DIR"]).iterdir():
        if not bookpath.is_dir():
            continue
        if bookpath.name.startswith("_"):
            continue
        try:
            book = Book(bookpath)
            _books[book.id] = book
        except FileNotFoundError:
            pass


def get_books(request):
    "Get list of all books readable by the current user, excluding '_refs'."
    return sorted(
        [
            b
            for b in _books.values()
            if auth.authorized(request, *auth.book_view_rules, book=b)
        ],
        key=lambda b: b.modified,
        reverse=True,
    )


def get_book(id, reread=False):
    "Get the book, optionally rereading it. No access test is made."
    global _books
    if not id:
        raise Error("no book identifier provided")
    try:
        book = _books[id]
        if reread:
            book.read()
        return book
    except KeyError:
        # May happen after update here of entire book.
        try:
            book = Book(Path(os.environ["WRITETHATBOOK_DIR"]) / id)
            _books[book.id] = book
            return book
        except FileNotFoundError:
            raise Error(f"no such book '{id}'", HTTP.NOT_FOUND)


def get_refs(reread=False):
    "Get the references book, optionally rereading it."
    global _refs
    if reread:
        _refs.read()
        _refs.items.sort(key=lambda r: r["id"])
        _refs.write()
    return _refs


def unpack_tgz_content(dirpath, content, is_refs=False):
    "Put contents of a TGZ file for a book into the given directory."
    try:
        tf = tarfile.open(fileobj=io.BytesIO(content), mode="r:gz")
        # Check validity: file 'index.md' must be included when not refs.
        if not is_refs and "index.md" not in tf.getnames():
            raise Error("missing 'index.md' file in TGZ file")
        # Check validity: possibly malicious paths.
        for name in tf.getnames():
            # Absolute path: possibly malicious?
            if Path(name).is_absolute():
                raise Error(f"reference TGZ file contains absolute file name '{name}'")
            # Attempt to navigate outside of directory: possibly malicious?
            if ".." in name:
                raise Error(
                    f"reference TGZ file contains disallowed file name '{name}'"
                )
        # When refs: Additional checks for validity.
        if is_refs:
            import apps

            rx = re.compile(apps.refs.RefConvertor.regex)
            for name in tf.getnames():
                if name == "index.md":
                    continue
                # No non-Markdown files allowed.
                if not name.endswith(".md"):
                    raise Error("refs TGZ file must contain only *.md files")
                # No subdirectories allowed.
                if Path(name).name != name:
                    raise Error("refs TGZ file must contain no directories")
                # File name must match reference id pattern.
                if not rx.match(Path(name).stem):
                    raise Error("refs TGZ file contains invalid file name '{name}'")
            # Skip 'index.md' and anything that is not a file.
            filter = lambda f, path: f if f.name != "index.md" and f.isfile() else None
        else:
            # Skip anything that is not a file or directory.
            filter = lambda f, path: f if f.isfile() or f.isdir() else None

        tf.extractall(path=dirpath, filter=filter)
    except tarfile.TarError as message:
        raise Error(f"tar file error: {message}")


class Container:
    "General container of frontmatter and Markdown content. To be inherited."

    def read_markdown(self, filepath):
        "Read frontmatter and content from the Markdown file."
        try:
            with open(filepath) as infile:
                content = infile.read()
        except FileNotFoundError:
            content = ""
        match = FRONTMATTER.match(content)
        if match:
            self.frontmatter = yaml.safe_load(match.group(1))
            self.content = content[match.start(2) :]
        else:
            self.frontmatter = {}
            self.content = content
 
    @property
    def subtitle(self):
        return self.frontmatter.get("subtitle")

    @subtitle.setter
    def subtitle(self, subtitle):
        self.frontmatter["subtitle"] = subtitle or None

    @property
    def html(self):
        return markdown.convert_to_html(self.content)

    @property
    def ast(self):
        return markdown.convert_to_ast(self.content)

    def write_markdown(self, filepath):
        "Write frontmatter and content to the Markdown file."
        with open(filepath, "w") as outfile:
            if self.frontmatter:
                outfile.write("---\n")
                outfile.write(yaml.dump(self.frontmatter, allow_unicode=True))
                outfile.write("---\n")
            if self.content:
                outfile.write(self.content)

    def update_markdown(self, content):
        """Update content. Return True if any change, else False.
        If non-None content, then clean it:
        - Strip each line from the right. (Markdown line breaks not allowed.)
        - Do not write out multiple consecutive empty lines.
        """
        if content is None:
            return False
        lines = []
        prev_empty = False
        for line in content.split("\n"):
            line = line.rstrip()
            empty = not bool(line)
            if empty and prev_empty:
                continue
            prev_empty = empty
            lines.append(line)
        content = "\n".join(lines)
        changed = content != self.content
        if changed:
            self.content = content
        return changed

    def get_digest_instance(self):
        "Return the digest instance having processed item frontmatter and content."
        frontmatter = self.frontmatter.copy()
        frontmatter.pop("digest", None)  # Necessary!
        digest = utils.get_digest_instance(json.dumps(frontmatter, sort_keys=True))
        digest = utils.get_digest_instance(self.content, digest=digest)
        return digest

    def get_copy_abspath(self):
        "Get the abspath for the next valid copy, and the number."
        stem = self.abspath.stem
        for number in [None] + list(range(2, constants.MAX_COPY_NUMBER + 1)):
            if number:
                newpath = self.abspath.with_name(f'{stem}_{Tx("copy*")}_{number}')
            else:
                newpath = self.abspath.with_name(f'{stem}_{Tx("copy*")}')
            if not (newpath.with_suffix(constants.MARKDOWN_EXT).exists() or
                    newpath.with_suffix("").exists()):
                return newpath.with_suffix(self.abspath.suffix), number
        else:
            raise Error("could not form copy identifier; too many copies")


class Book(Container):
    "Root container for Markdown book texts in files and directories."

    def __init__(self, abspath):
        self.abspath = abspath
        self.read()

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"Book('{self.id}')"

    def __getitem__(self, path):
        "Return the item (section or text) given its URL path."
        try:
            return self.path_lookup[path]
        except KeyError:
            raise Error(f"no such text '{path}'", HTTP.NOT_FOUND)

    def __iter__(self):
        for item in self.items:
            yield item
            if item.is_section:
                yield from item

    def read(self):
        """ "Read the book from file.
        All items (sections, texts) recursively from files.
        Set up indexed and references lookups.
        """
        self.read_markdown(self.absfilepath)

        self.items = []

        # Section and Text instances for directories and files that actually exist.
        for path in sorted(self.abspath.iterdir()):

            # Skip emacs temporary files.
            if path.name.startswith("#"):
                continue
            if path.name.startswith(".#"):
                continue

            # Do not include 'index.md' file; handled separately.
            if path.name == "index.md":
                continue

            # Recursively read all items beneath this one.
            if path.is_dir():
                self.items.append(Section(self, self, path.name))

            elif path.suffix == constants.MARKDOWN_EXT:
                item = Text(self, self, path.stem)
                if not item.frontmatter.get("exclude"):
                    self.items.append(item)

            # Ignore other files.
            else:
                pass

        # Set the order to be that explicity given, if any.
        self.set_items_order(self, self.frontmatter.get("items", []))

        # Key: item path; value: item.
        self.path_lookup = {}
        for item in self:
            self.path_lookup[item.path] = item

        # Index key: indexed term; value: set of texts.
        # Refs key: reference identifier; value: set of texts.
        self.indexed = {}
        self.refs = {}
        ast = self.ast  # Compiled when called.
        self.find_indexed(self, ast)
        for item in self:
            ast = item.ast  # Compiled when called.
            self.find_indexed(item, ast)
            for keyword in item.get("keywords", []):
                self.indexed.setdefault(keyword, set()).add(item)
            self.find_refs(item, ast)

        # Write out "index.md" if order changed.
        self.write()

    def write(self, content=None, force=False):
        """Write the 'index.md' file, if changed.
        If 'content' is not None, then update it.
        """
        changed = self.update_markdown(content)
        original = copy.deepcopy(self.frontmatter)
        self.frontmatter["items"] = self.get_items_order(self)
        self.frontmatter["type"] = self.type
        self.frontmatter["status"] = repr(self.status)
        self.frontmatter["sum_characters"] = self.sum_characters
        self.frontmatter["digest"] = self.digest
        if changed or force or (self.frontmatter != original):
            self.write_markdown(self.absfilepath)

    def set_items_order(self, container, items_order):
        "Chnage order of items in container according to given items_order."
        original = dict([i.name, i] for i in container.items)
        container.items = []
        for ordered in items_order:
            try:
                item = original.pop(ordered["name"])
            except KeyError:
                pass
            else:
                container.items.append(item)
                if isinstance(item, Section):
                    self.set_items_order(item, ordered.get("items", []))
        # Append items not already referenced in the frontmatter 'items'.
        container.items.extend(original.values())

    def get_items_order(self, container):
        "Return current order of items in this book."
        result = []
        for item in container.items:
            if item.is_text:
                result.append(dict(name=item.name, title=item.title))
            elif item.is_section:
                result.append(
                    dict(
                        name=item.name,
                        title=item.title,
                        items=self.get_items_order(item),
                    )
                )
        return result

    @property
    def id(self):
        "The identifier of the book instance is not stored in its 'index.md'."
        return self.abspath.name

    @property
    def absfilepath(self):
        "Return the absolute file path of the 'index.md' file."
        return self.abspath / "index.md"

    @property
    def title(self):
        return self.frontmatter.get("title") or self.id

    @title.setter
    def title(self, title):
        self.frontmatter["title"] = title or None

    @property
    def fulltitle(self):
        return Tx("Book")

    @property
    def path(self):
        "Required for the recursive call sequence from below."
        return ""

    @property
    def type(self):
        return constants.BOOK if len(self.items) else constants.ARTICLE

    @property
    def modified(self):
        return utils.timestr(filepath=self.absfilepath)

    @property
    def owner(self):
        return self.frontmatter.get("owner")

    @owner.setter
    def owner(self, userid):
        if not users.get(userid):
            raise ValueError("no such user '{userid]'")
        self.frontmatter["owner"] = userid

    @property
    def public(self):
        return bool(self.frontmatter.get("public"))

    @public.setter
    def public(self, yes):
        self.frontmatter["public"] = bool(yes)

    @property
    def status(self):
        "Return the lowest status for the sub-items, or from 'index.md' if no items."
        if self.items:
            status = constants.FINAL
            for item in self.items:
                status = min(status, item.status)
        else:
            status = constants.Status.lookup(
                self.frontmatter.get("status"), constants.STARTED
            )
        return status

    @status.setter
    def status(self, status):
        "If this is an article, then set the status."
        if len(self.items) != 0:
            raise ValueError("Cannot set status for book with items.")
        if type(status) == str:
            status = constants.Status.lookup(status)
            if status is None:
                raise ValueError("Invalid status value.")
        elif not isinstance(status, constants.Status):
            raise ValueError("Invalid instance for status.")
        self.frontmatter["status"] = repr(status)

    @property
    def authors(self):
        return self.frontmatter.get("authors") or []

    @authors.setter
    def authors(self, authors):
        if not isinstance(authors, list):
            raise TypeError("authors must be a list")
        self.frontmatter["authors"] = authors

    @property
    def language(self):
        return self.frontmatter.get("language")

    @language.setter
    def language(self, language):
        self.frontmatter["language"] = language or None

    @property
    def parent(self):
        return None

    @property
    def level(self):
        return 0

    @property
    def max_level(self):
        return max([i.level for i in self])

    @property
    def n_words(self):
        "Approximate number of words in the 'index.md' of this book."
        return len(self.content.split())

    @property
    def sum_words(self):
        "Approximate number of words in the entire book."
        return sum([i.sum_words for i in self.items]) + len(self.content.split())

    @property
    def n_characters(self):
        "Approximate number of characters in the 'index.md' of this book."
        return len(self.content)

    @property
    def sum_characters(self):
        "Approximate number of characters in the entire book."
        return sum([i.sum_characters for i in self.items]) + len(self.content)

    @property
    def docx(self):
        return self.frontmatter.get("docx") or {}

    @property
    def pdf(self):
        return self.frontmatter.get("pdf") or {}

    @property
    def state(self):
        "Return a dictionary of the current state of the book."
        return dict(
            type="book",
            id=self.id,
            title=self.title,
            modified=utils.timestr(
                filepath=self.absfilepath, localtime=False, display=False
            ),
            n_characters=self.n_characters,
            sum_characters=self.sum_characters,
            digest=self.digest,
            items=[i.state for i in self.items],
        )

    @property
    def digest(self):
        """Return the hex digest of the contents of the book.
        Based on frontmatter (excluding digest!), content, and digests of items.
        """
        digest = self.get_digest_instance()
        for item in self.items:
            utils.get_digest_instance(item.digest, digest=digest)
        return digest.hexdigest()

    @property
    def ordinal(self):
        return (0,)

    def find_indexed(self, item, ast):
        "Return the indexed terms in the AST of the content."
        try:
            for child in ast["children"]:
                if isinstance(child, str):
                    continue
                if child["element"] == "indexed":
                    self.indexed.setdefault(child["canonical"], set()).add(item)
                self.find_indexed(item, child)
        except KeyError:
            pass

    def find_refs(self, item, ast):
        "Return the references in the AST of the content."
        try:
            for child in ast["children"]:
                if isinstance(child, str):
                    continue
                if child["element"] == "reference":
                    self.refs.setdefault(child["id"], set()).add(item)
                self.find_refs(item, child)
        except KeyError:
            pass

    def get(self, path, default=None):
        "Return the item given its path."
        return self.path_lookup.get(path, default)

    def create_section(self, title, parent=None):
        """Create a new empty section inside the book or parent section.
        Raise Error if there is a problem.
        """
        assert parent is None or isinstance(parent, Section) or isinstance(parent, Book)
        if parent is None:
            parent = self
        name = utils.nameify(title)
        dirpath = parent.abspath / name
        filepath = dirpath.with_suffix(constants.MARKDOWN_EXT)
        if dirpath.exists() or filepath.exists():
            raise Error(f"The title '{title}' is already used within '{parent}'.")
        dirpath.mkdir()
        section = Section(self, parent, name)
        section.title = title
        parent.items.append(section)
        self.path_lookup[section.path] = section
        section.write()
        self.write()
        return section

    def create_text(self, title, parent=None):
        """Create a new empty text inside the book or parent section.
        Raise ValueError if there is a problem.
        """
        assert parent is None or isinstance(parent, Section) or isinstance(parent, Book)
        if parent is None:
            parent = self
        name = utils.nameify(title)
        dirpath = parent.abspath / name
        filepath = dirpath.with_suffix(constants.MARKDOWN_EXT)
        if dirpath.exists() or filepath.exists():
            raise Error(f"The title '{title}' is already used within '{parent}'.")
        text = Text(self, parent, name)
        text.title = title
        parent.items.append(text)
        self.path_lookup[text.path] = text
        text.write()
        self.write()
        return text

    def merge(self, path):
        "Merge the section with all its subitems into a text. Return the text."
        section = self[path]
        if not section.is_section:
            raise Error(f"Item '{item}' is not a section; cannot merge.")
        content, footnotes = section.split_footnotes()
        merged_content = [content]
        merged_footnotes = [footnotes]
        for item in section:
            content, footnotes = item.split_footnotes()
            merged_content.append(f"\n\n{'#' * item.level} {item.title}\n\n")
            merged_content.append(content)
            merged_footnotes.append(footnotes)
        title = section.title
        status = section.status
        parent = section.parent
        position = section.index
        section.delete(force=True)
        text = self.create_text(title, parent=parent)
        text.status = status
        text.write(content="\n\n".join(merged_content + merged_footnotes))
        while text.index != position:
            text.backward()
        self.write()
        return text

    def split(self, path):
        "Split the text into a section with subtexts. Return the section."
        text = self[path]
        if not text.is_text:
            raise Error(f"Item '{item}' is not a text; cannot split.")
        # Collect all footnotes to be partitioned among the texts.
        content, footnotes = text.split_footnotes()
        footnotes_lookup = {}
        key = None
        footnote = []
        for line in footnotes.split("\n"):
            if line.startswith("[^"):
                if key and footnote:
                    footnotes_lookup[key] = "\n".join(footnote)
                key = line[:line.index("]:")-1]
                footnote = []
            if key:
                footnote.append(line)
        if key and footnote:
            footnotes_lookup[key] = "\n".join(footnote)
        # Split up content according to headers.
        parts = []
        title = None
        part = []
        for line in content.split("\n"):
            if line.startswith("#"):
                parts.append([title, part]) # First title is None.
                part = []
                title = line.strip("#").strip()
            else:
                part.append(line)
        if title and part:
            parts.append([title, part])
        title = text.title
        status = text.status
        parent = text.parent
        position = text.index
        text.delete(force=True)
        section = self.create_section(title, parent=parent)
        for title, content in parts:
            content = "\n".join(content)
            footnotes = []
            for key, footnote in footnotes_lookup.items():
                if key in content:
                    footnotes.append(footnote)
            if footnotes:
                content += "\n\n" + "\n\n".join(footnotes)
            if title is None:
                section.write(content=content)
            else:
                text = self.create_text(title, parent=section)
                text.status = status
                text.write(content=content)
        while section.index != position:
            section.backward()
        self.write()
        return section

    def copy(self, owner=None):
        "Make a copy of the book."
        abspath, number = self.get_copy_abspath()
        try:
            shutil.copytree(self.abspath, abspath)
        except shutil.Error as error:
            raise Error(error, HTTP.CONFLICT)
        book = Book(abspath)
        if number:
            book.title = f'{self.title} ({Tx("copy*")} {number})'
        else:
            book.title = f'{self.title} ({Tx("copy*")})'
        if owner:
            book.frontmatter["owner"] = owner
        book.write()
        get_refs(reread=True)
        _books[book.id] = book
        return book

    def delete(self, force=False):
        "Delete the book."
        global _books
        if not force and len(self.items) != 0:
            raise ValueError("Cannot delete non-empty book.")
        _books.pop(self.id, None)
        shutil.rmtree(self.abspath)
        get_refs(reread=True)

    def get_tgz_content(self):
        """Return the contents of the gzipped tar file containing
        all files for the items of this book.
        """
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tgzfile:
            tgzfile.add(self.absfilepath, arcname="index.md")
            for item in self.items:
                tgzfile.add(item.abspath, arcname=item.filename(), recursive=True)
        return buffer.getvalue()

    def search(self, term, ignorecase=True):
        "Find the set of items that contain the term in the content."
        if ignorecase:
            flags = re.IGNORECASE
        else:
            flags = 0
        result = set()
        if re.search(term, self.content, flags):
            result.add(self)
        for item in self.items:
            result.update(item.search(term, ignorecase=ignorecase))
        return result

    def check_integrity(self):
        assert self.absfilepath.exists()
        assert self.absfilepath.is_file()
        assert self.abspath.exists()
        assert self.abspath.is_dir()
        assert len(self.path_lookup) == len(list(self))
        for item in self:
            assert item.book is self, (self, item)
            assert isinstance(item, Text) or isinstance(item, Section), (self, item)
            item.check_integrity()


class Item(Container):
    "Abstract class for sections and texts."

    def __init__(self, book, parent, name):
        self.book = book
        self.parent = parent
        self._name = name
        self.read()

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.path}')"

    def __getitem__(self, key):
        return self.frontmatter[key]

    def __setitem__(self, key, value):
        self.frontmatter[key] = value

    def __iter__(self):
        for item in self.items:
            yield item
            yield from item

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def set(self, key, value):
        "Set the item in the frontmatter, or delete it."
        if value:
            self.frontmatter[key] = value
        else:
            self.frontmatter.pop(key, None)

    def read(self):
        "To be implemented by inheriting classes. Recursive."
        raise NotImplementedError

    def write(self, content=None, force=False):
        "To be implemented by inheriting classes. *Not* recursive."
        raise NotImplementedError

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        """Set the name for the item.
        Changes the file or directory name of the item.
        Raise ValueError if any problem.
        """
        name = utils.nameify(name)
        if name == self.name:
            return
        if not name:
            raise ValueError("Empty string given for name.")
        newabspath = self.parent.abspath / self.filename(new=name)
        if name in self.parent.items or newabspath.exists():
            raise ValueError("The name is already in use.")
        items = [self]
        if self.is_section:
            items.extend(list(self))
        for item in items:
            self.book.path_lookup.pop(item.path)
        oldabspath = self.abspath
        self._name = name
        oldabspath.rename(newabspath)
        for item in items:
            self.book.path_lookup[item.path] = item
        self.book.write()

    @property
    def path(self):
        "The URL path to this item, without leading '/'. Concatenated names."
        if self.parent is self.book:
            return self.name
        else:
            return f"{self.parent.path}/{self.name}"

    @property
    def title(self):
        return self.frontmatter.get("title") or self.name

    @title.setter
    def title(self, title):
        self.frontmatter["title"] = title

    @property
    def fulltitle(self):
        "Concatenated title for this item."
        if self.parent is self.book:
            return self.title
        else:
            return f"{self.parent.fulltitle}; {self.title}"

    @property
    def level(self):
        return self.parent.level + 1

    @property
    def type(self):
        raise NotImplementedError

    @property
    def is_text(self):
        return self.type == constants.TEXT

    @property
    def is_section(self):
        return self.type == constants.SECTION

    @property
    def index(self):
        "The zero-based position of this item among its siblings."
        for count, item in enumerate(self.parent.items):
            if item is self:
                return count

    @property
    def digest(self):
        """Return the hex digest of the contents of the item.
        Based on frontmatter (excluding 'digest!') and content of the item.
        Does not include any data from the subitems.
        """
        return self.get_digest_instance().hexdigest()

    @property
    def ordinal(self):
        "Tuple of parent's and its own index for sorting purposes."
        result = [self.index + 1]
        parent = self.parent
        while parent is not self.book:
            result.append(parent.index + 1)
            parent = parent.parent
        return tuple(reversed(result))

    @property
    def heading(self):
        "Title preceded by ordinal."
        return f'{".".join([str(i) for i in self.ordinal])}. {self.title}'

    @property
    def prev(self):
        "Previous sibling or None."
        index = self.index
        if index == 0:
            return None
        return self.parent.items[index - 1]

    @property
    def prev_section(self):
        "Return the section sibling that closest backward to it, if any."
        index = self.index
        while index:
            item = self.parent.items[index - 1]
            if item.is_section:
                return item
            index -= 1
        return None

    @property
    def next(self):
        "Next sibling or None."
        try:
            return self.parent.items[self.index + 1]
        except IndexError:
            return None

    @property
    def chapter(self):
        "Top-level section or text for this item; possibly itself."
        item = self
        while item.parent is not self.book:
            item = item.parent
        return item

    @property
    def abspath(self):
        """The absolute path for this item.
        - Section: Directory path.
        - Text: File path.
        """
        return self.parent.abspath / self.filename()

    @property
    def absfilepath(self):
        """The absolute filepath ot this item.
        - Section: File path to 'index.md'.
        - Text: File path.
        To be implemented by inheriting classes.
        """
        raise NotImplementedError

    @property
    def language(self):
        return self.book.language

    def split_footnotes(self):
        "Return content split up as a tuple (text, footnotes)."
        lines = self.content.split("\n")
        for pos, line in enumerate(lines):
            if line.startswith("[^"):
                return ("\n".join(lines[:pos]), "\n".join(lines[pos:]))
        else:
            return (self.content, "")

    def filename(self, newname=None):
        """Return the filename of this item.
        Note: this is not the path, just the base name of the file or directory.
        To be implemented by inheriting classes.
        """
        raise NotImplementedError

    def forward(self):
        "Move this item forward in its list of siblings. Loop around at end."
        index = self.index
        item = self.parent.items.pop(index)
        if index == len(self.parent.items):
            self.parent.items.insert(0, item)
        else:
            self.parent.items.insert(index + 1, item)
        # Write out book 'index.md' containing new order.
        self.book.write()

    def backward(self):
        "Move this item backward in its list of siblings. Loop around at beginning."
        index = self.index
        item = self.parent.items.pop(index)
        if index == 0:
            self.parent.items.append(item)
        else:
            self.parent.items.insert(index - 1, item)
        # Write out book 'index.md' containing new order.
        self.book.write()

    def outof(self):
        "Move this item out of its section into the section or book above."
        if self.parent is self.book:
            return
        old_abspath = self.abspath
        new_abspath = self.parent.parent.abspath / self.filename()
        # Must check both file and directory for name collision.
        for path in [
            new_abspath,
            new_abspath.with_suffix(""),
            new_abspath.with_suffix(constants.MARKDOWN_EXT),
        ]:  # Doesn't matter if '.md.md'
            if path.exists():
                raise Error(
                    "cannot move item; name collision with an existing item",
                    HTTP.CONFLICT,
                )
        # Remove item and all its subitems from the path lookup of the book.
        self.book.path_lookup.pop(self.path)
        for item in self:
            self.book.path_lookup.pop(item.path)
        # Remove item from its parent's list of items.
        self.parent.items.remove(self)
        # Actually move the item on disk.
        old_abspath.rename(new_abspath)
        # Add item into the parent above, after the position of its old parent.
        pos = self.parent.parent.items.index(self.parent) + 1
        self.parent.parent.items.insert(pos, self)
        # Set the new parent for this item.
        self.parent = self.parent.parent
        # Add back this item and its subitems to the path lookup of the book.
        self.book.path_lookup[self.path] = self
        for item in self:
            self.book.path_lookup[item.path] = item
        self.check_integrity()
        # Write out book and reread everything; refs and indexes must be updated.
        self.book.write()
        self.book.read()
        get_refs(reread=True)

    def into(self):
        "Move this item into the section closest backward of it."
        section = self.prev_section
        if not section:
            return
        old_abspath = self.abspath
        new_abspath = section.abspath / self.filename()
        # Must check both file and directory for name collision.
        for path in [
            new_abspath,
            new_abspath.with_suffix(""),
            new_abspath.with_suffix(constants.MARKDOWN_EXT),
        ]:  # Doesn't matter if '.md.md'
            if path.exists():
                raise Error(
                    "cannot move item; name collision with an existing item",
                    HTTP.CONFLICT,
                )
        # Remove item and all its subitems from the path lookup of the book.
        self.book.path_lookup.pop(self.path)
        for item in self:
            self.book.path_lookup.pop(item.path)
        # Remove item from its parent's list of items.
        self.parent.items.remove(self)
        # Actually move the item on disk.
        old_abspath.rename(new_abspath)
        # Add item into the section, as the last one.
        section.items.append(self)
        # Set the new parent for this item.
        self.parent = section
        # Add back this item and its subitems to the path lookup of the book.
        self.book.path_lookup[self.path] = self
        for item in self:
            self.book.path_lookup[item.path] = item
        self.check_integrity()
        # Write out book and reread everything; refs and indexes must be updated.
        self.book.write()
        self.book.read()
        get_refs(reread=True)

    def copy(self):
        "Copy this item."
        raise NotImplementedError

    def delete(self):
        "Delete this item from the book."
        raise NotImplementedError

    def search(self, term, ignorecase=True):
        "Find the set of items that contain the term in the content."
        raise NotImplementedError

    def check_integrity(self):
        assert isinstance(self.book, Book)
        assert self in self.parent.items
        assert self.path in self.book.path_lookup
        assert self.abspath.exists()


class Section(Item):
    "Directory containing other directories and Markdown text files"

    def __init__(self, book, parent, name):
        self.items = []
        super().__init__(book, parent, name)

    def read(self):
        """Read all items in the subdirectory, and the 'index.md' file, if any.
        This is recursive; all sections and texts below this are also read.
        """
        self.read_markdown(self.absfilepath)
        for path in sorted(self.abspath.iterdir()):

            # Skip temporary emacs files.
            if path.name.startswith("#"):
                continue
            if path.name.startswith(".#"):
                continue

            # Skip the already read 'index.md' file.
            if path.name == "index.md":
                continue

            # Recursively read all items beneath this one.
            if path.is_dir():
                self.items.append(Section(self.book, self, path.name))

            elif path.suffix == constants.MARKDOWN_EXT:
                self.items.append(Text(self.book, self, path.stem))

            # Ignore other files.
            else:
                pass

        # Repair if no 'index.md' in the directory.
        if not self.absfilepath.exists():
            self.write_markdown(self.absfilepath)

    def write(self, content=None, force=False):
        """Write the 'index.md' file, if changed.
        If 'content' is not None, then update it.
        This is *not* recursive.
        """
        changed = self.update_markdown(content)
        original = copy.deepcopy(self.frontmatter)
        self.frontmatter["digest"] = self.digest
        if changed or force or (self.frontmatter != original):
            self.write_markdown(self.absfilepath)

    @property
    def type(self):
        return constants.SECTION

    @property
    def n_words(self):
        "Approximate number of words in 'index.md' of this section."
        return len(self.content.split())

    @property
    def sum_words(self):
        "Approximate number of words in the entire section."
        return sum([i.sum_words for i in self.items]) + len(self.content.split())

    @property
    def n_characters(self):
        "Approximate number of characters in the 'index.md' of this section."
        return len(self.content)

    @property
    def sum_characters(self):
        "Approximate number of characters in the entire section."
        return sum([i.sum_characters for i in self.items]) + len(self.content)

    @property
    def modified(self):
        return utils.timestr(filepath=self.absfilepath)

    @property
    def status(self):
        "Return the lowest status for the sub-items."
        if self.items:
            status = constants.FINAL
            for item in self.items:
                status = min(status, item.status)
        else:
            status = constants.STATUSES[0]
        return status

    @property
    def state(self):
        "Return a dictionary of the current state of the section."
        return dict(
            type=constants.SECTION,
            name=self.name,
            title=self.title,
            modified=utils.timestr(
                filepath=self.absfilepath, localtime=False, display=False
            ),
            n_characters=self.n_characters,
            digest=self.digest,
            items=[i.state for i in self.items],
        )

    @property
    def absfilepath(self):
        "The absolute filepath of the 'index.md' for this section."
        return self.abspath / "index.md"

    def filename(self, new=None):
        """Return the filename of this section.
        Note: this is not the path, just the base name of the directory.
        """
        if new:
            return utils.nameify(new)
        else:
            return self.name

    def copy(self):
        "Make a copy of this section and all below it."
        abspath, number = self.get_copy_abspath()
        try:
            shutil.copytree(self.abspath, abspath)
        except shutil.Error as error:
            raise Error(error, HTTP.CONFLICT)
        section = Section(self.book, self.parent, abspath.stem)
        if number:
            section.frontmatter["title"] = f'{self.title} ({Tx("copy*")} {number})'
        else:
            section.frontmatter["title"] = f'{self.title} ({Tx("copy*")})'
        self.parent.items.insert(self.index + 1, section)
        section.write()
        path = section.path
        self.book.write()
        self.book.read()
        get_refs(reread=True)
        return path

    def delete(self, force=False):
        "Delete this section from the book."
        if not force and len(self.items) != 0:
            raise ValueError("Cannot delete non-empty section.")
        self.book.path_lookup.pop(self.path)
        self.parent.items.remove(self)
        shutil.rmtree(self.abspath)
        self.book.write()
        get_refs(reread=True)

    def search(self, term, ignorecase=True):
        "Find the set of items that contain the term in the content."
        if ignorecase:
            flags = re.IGNORECASE
        else:
            flags = 0
        result = set()
        if re.search(term, self.content, flags):
            result.add(self)
        for item in self.items:
            result.update(item.search(term, ignorecase=ignorecase))
        return result

    def check_integrity(self):
        super().check_integrity()
        assert self.abspath.is_dir()


class Text(Item):
    "Markdown file."

    def read(self):
        "Read the frontmatter (if any) and content from the Markdown file."
        self.read_markdown(self.abspath)

    def write(self, content=None, force=False):
        """Write the text, if changed.
        If 'content' is not None, then update it.
        """
        changed = self.update_markdown(content)
        original = copy.deepcopy(self.frontmatter)
        self.frontmatter["digest"] = self.digest
        if changed or force or (self.frontmatter != original):
            self.write_markdown(self.abspath)

    @property
    def type(self):
        return constants.TEXT

    @property
    def items(self):
        "All immediate subitems (none). Instead of an empty list attribute."
        return []

    @property
    def n_words(self):
        "Approximate number of words in the text."
        return len(self.content.split())

    @property
    def sum_words(self):
        "Approximate number of words in the text."
        return self.n_words

    @property
    def n_characters(self):
        "Approximate number of characters in the text."
        return len(self.content)

    @property
    def sum_characters(self):
        "Approximate number of characters in the text."
        return self.n_characters

    @property
    def modified(self):
        return utils.timestr(filepath=self.abspath)

    @property
    def status(self):
        return constants.Status.lookup(
            self.frontmatter.get("status"), constants.STARTED
        )

    @status.setter
    def status(self, status):
        if type(status) == str:
            status = constants.Status.lookup(status)
            if status is None:
                raise ValueError("Invalid status value.")
        elif not isinstance(status, constants.Status):
            raise ValueError("Invalid instance for status.")
        self.frontmatter["status"] = repr(status)

    @property
    def state(self):
        "Return a dictionary of the current state of the text."
        return dict(
            type=constants.TEXT,
            name=self.name,
            title=self.title,
            modified=utils.timestr(
                filepath=self.abspath, localtime=False, display=False
            ),
            n_characters=self.n_characters,
            digest=self.digest,
        )

    @property
    def absfilepath(self):
        "The absolute filepath ot this text."
        return self.abspath

    def filename(self, new=None):
        """Return the filename of this text; optionally if the new title were set.
        Note: this is not the path, just the base name of the file.
        """
        if new:
            return utils.nameify(new) + constants.MARKDOWN_EXT
        else:
            return self.name + constants.MARKDOWN_EXT

    def copy(self):
        "Make a copy of this text."
        abspath, number = self.get_copy_abspath()
        try:
            shutil.copy2(self.abspath, abspath)
        except shutil.Error as error:
            raise Error(error, HTTP.CONFLICT)

        text = Text(self.book, self.parent, abspath.stem)
        if number:
            text.frontmatter["title"] = f'{self.title} ({Tx("copy*")} {number})'
        else:
            text.frontmatter["title"] = f'{self.title} ({Tx("copy*")})'
        self.parent.items.insert(self.index + 1, text)
        text.write()
        path = text.path
        self.book.write()
        self.book.read()
        get_refs(reread=True)
        return path

    def delete(self, force=False):
        "Delete this text from the book."
        self.book.path_lookup.pop(self.path)
        self.parent.items.remove(self)
        self.abspath.unlink()
        self.book.write()

    def search(self, term, ignorecase=True):
        "Find the set of items that contain the term in the content."
        if ignorecase:
            flags = re.IGNORECASE
        else:
            flags = 0
        if re.search(term, self.content, flags):
            return set([self])
        else:
            return set()

    def check_integrity(self):
        super().check_integrity()
        assert self.abspath.is_file()

if __name__ == "__main__":
    book = Book(Path(os.environ["WRITETHATBOOK_DIR"]) / "test")
    for item in book:
        print(item)
    print(list(book))
    newpath = Path(os.environ["WRITETHATBOOK_DIR"]) / "test2"
    os.mkdir(newpath)
    book = Book(newpath)
    print(list(book), bool(book))
