import shutil
from pathlib import Path
from typing import Type

import dominate
import dominate.tags
from dominate.tags import (
    style,
    link,
    meta,
    script,
    body,
    div,
    h1,
    table,
    colgroup,
    col,
    tbody,
    tr,
    td,
    p,
    strong,
    a,
    hr,
    ul,
    li,
    thead,
    th,
    em,
    span,
)
from dominate.util import raw
from rdflib import (
    Graph,
    OWL,
    SDO,
    DCTERMS,
    VANN,
    SKOS,
)

from pylode.utils import (
    PylodeError,
    load_ontology,
)
from pylode.profiles.supermodel.query import Query
from pylode.profiles.supermodel.model import ComponentModel, Class, RDFProperty
from pylode.profiles.supermodel.component import (
    metadata_row,
    h2,
    h3,
    h4,
    h5,
    h6,
    external_link,
    example,
)
from pylode.profiles.supermodel.fragment import make_html_fragment

RDF_FOLDER = Path(__file__).parent / "rdf"

MODULE_STRING = "Module: {}"
CLASS_STRING = "{}"
ANNOTATION_PROPERTY_STRING = "{}"


def is_heading(doc: dominate.document) -> bool:
    if isinstance(
        doc,
        (
            dominate.tags.h2,
            dominate.tags.h3,
            dominate.tags.h4,
        ),
    ):
        return True
    return False


def get_headings(doc: dominate.document) -> list:
    headings = []
    if hasattr(doc, "children"):
        for child in doc.children:
            if is_heading(child):
                headings.append(child)
            else:
                headings += get_headings(child)
    return headings


class Supermodel:
    def __init__(
        self, ontology: Graph | Path | str, QueryClass: Type[Query] = Query
    ) -> None:
        self.ont = load_ontology(ontology)
        self.query = QueryClass(self.ont)

        self.toc: dict[str, str] = {}
        self.fids: dict[str, str] = {}
        self.ns = self.query.ns
        self.iri = self.query.get_supermodel_iri()

        # make HTML doc with title
        title = self.query.get_title(self.iri)
        if title is None:
            raise PylodeError(
                "You MUST supply a title property "
                "(dcterms:title, rdf:label or sdo:name) for your ontology"
            )
        self.doc = dominate.document(title=title)

    def make_html(self, destination: Path = None, include_css: bool = True):
        self._make_head(
            self.query.get_schema_org_metadata_graph(),
            include_css=include_css,
            destination=destination,
        )
        self._make_body()
        self._make_toc()

        if destination is not None:
            open(destination, "w").write(self.doc.render())
        else:
            return self.doc.render()

    def _make_toc(self):
        def heading_value_component(
            heading: dominate.tags.h2 | dominate.tags.h3 | dominate.tags.h4,
            value: str,
        ):
            with li() as component:
                href = (
                    f"#{heading.attributes.get('id')}"
                    if heading.attributes.get("id")
                    else "#"
                )
                a(value, href=href)

            return component

        headings = get_headings(self.doc)

        with self.header:
            with div(_class="toc2", id="toc"):
                div("Table of Contents", id="toctitle")
                top_unordered_list = ul(_class="sectlevel1")

        index = {}
        section_numbers = {
            1: 0,
            2: 0,
            3: 0,
            4: 0,
        }
        previous_heading = None
        for heading in headings:
            if previous_heading is None:
                previous_heading_level = 2
                index[2] = top_unordered_list
            else:
                previous_heading_level = int(str(type(previous_heading))[-3:-2])

            heading_level = int(str(type(heading))[-3:-2])

            section_numbers[heading_level - 1] += 1

            if previous_heading_level < heading_level:
                section_numbers[heading_level - 1] = 1

            section_number = ""
            if heading_level - 1 == 1:
                major = section_numbers[1]
                section_number = f"{major}. "
            elif heading_level - 1 == 2:
                major = section_numbers[1]
                minor = section_numbers[2]
                section_number = f"{major}.{minor}. "
            elif heading_level - 1 == 3:
                major = section_numbers[1]
                minor = section_numbers[2]
                patch = section_numbers[3]
                section_number = f"{major}.{minor}.{patch}. "

            if len(heading.children) > 1:
                if len(heading.children[1].children) > 0:
                    value = heading.children[1].children[0]
            elif len(heading.children) == 1 and isinstance(heading.children[0], str):
                value = heading.children[0]
            else:
                value = ""

            value = f"{section_number}{value}"

            if previous_heading_level == heading_level:
                level = index.get(heading_level)
                level = level if level is not None else level
                unordered_list = index[heading_level]
                with unordered_list:
                    heading_value_component(heading, value)
            elif previous_heading_level < heading_level:
                with ul(_class="mb-0") as unordered_list:
                    heading_value = heading_value_component(heading, value)
                    index[heading_level - 1].add(unordered_list)
                    index[heading_level] = heading_value
            else:
                unordered_list = index[heading_level]
                with unordered_list:
                    heading_value = heading_value_component(heading, value)
                    index[heading_level] = heading_value

            previous_heading = heading

    def _make_body(self):
        self.body: body = self.doc.add(body(_class="book toc2 toc-left"))

        self._make_header(self.query.onts_props[DCTERMS.title])
        self._make_content()

    def _make_header(self, title: str):
        self.header: div = self.body.add(div(id="header"))
        self.header.add(h1(title))

    def _make_content(self):
        self.content = self.body.add(div(id="content"))
        self._make_preamble()
        self._make_examples()
        self._make_component_models()

    def _make_component_model_class(self, cls: Class):
        with div(_class="sect3"):
            h4(CLASS_STRING.format(cls.name), True)

            with p("IRI:", _class="overflow-x-auto"):
                external_link(cls.iri, href=cls.iri)

            if cls.description:
                with div(_class="paragraph"):
                    p(cls.description)

            if cls.notes:
                for note in cls.notes:
                    with div(_class="admonitionblock note"):
                        with table():
                            with tbody():
                                with tr():
                                    with td(_class="icon"):
                                        div(note.type, _class="title")
                                    td(note.value, _class="content")

            if cls.is_defined_by is not None:
                with p("Is defined by "):
                    a(cls.is_defined_by.name, href=cls.is_defined_by.iri)

            if cls.superclasses:
                h5("Subclass of")
                with div(_class="sect5"):
                    with div(_class="ulist"):
                        with ul():
                            for subclass in cls.superclasses:
                                with li():
                                    with p():
                                        if subclass.iri in self.query.class_index:
                                            fragment = make_html_fragment(
                                                CLASS_STRING.format(subclass.name)
                                            )
                                            a(
                                                subclass.name,
                                                href=f"#{fragment}",
                                            )
                                        else:
                                            external_link(subclass.name, subclass.iri)

            if cls.subclasses:
                h5("Superclass of")
                with div(_class="sect5"):
                    with div(_class="ulist"):
                        with ul():
                            for subclass in cls.subclasses:
                                with li():
                                    with p():
                                        if subclass.iri in self.query.class_index:
                                            fragment = make_html_fragment(
                                                CLASS_STRING.format(subclass.name)
                                            )
                                            a(
                                                subclass.name,
                                                href=f"#{fragment}",
                                            )
                                        else:
                                            external_link(subclass.name, subclass.iri)

            if cls.properties:
                h5("Properties")
                with div(_class="sect5 overflow-x-auto"):
                    with table(
                        _class="tableblock frame-all grid-all stripes-even fit-content stretch"
                    ):
                        with thead():
                            with tr():
                                th(
                                    "Property",
                                    _class="tableblock halign-left valign-top",
                                )
                                th(
                                    "Description",
                                    _class="tableblock halign-left valign-top",
                                )
                                th(
                                    "Cardinality",
                                    _class="tableblock halign-left valign-top",
                                )
                                th(
                                    "Value type",
                                    _class="tableblock halign-left valign-top",
                                )
                                th(
                                    "Value class type",
                                    _class="tableblock halign-left valign-top",
                                )
                        with tbody():
                            for property in cls.properties:
                                with tr():
                                    with td(_class="tableblock halign-left valign-top"):
                                        fragment = make_html_fragment(
                                            CLASS_STRING.format(property.name)
                                        )
                                        a(property.name, href=f"#{fragment}")

                                        if property.belongs_to_class is not None:
                                            with p(_class="tableblock"):
                                                with em("From "):
                                                    fragment = make_html_fragment(
                                                        CLASS_STRING.format(
                                                            property.belongs_to_class.name
                                                        )
                                                    )
                                                    a(
                                                        property.belongs_to_class.name,
                                                        href=f"#{fragment}",
                                                    )
                                    with td(_class="tableblock halign-left valign-top"):
                                        p(property.description)
                                    with td(_class="tableblock halign-left valign-top"):
                                        if (
                                            property.cardinality_min is None
                                            and property.cardinality_max is None
                                        ):
                                            p("[0..*]", _class="tableblock")
                                        elif (
                                            property.cardinality_min is None
                                            and isinstance(
                                                property.cardinality_max, int
                                            )
                                        ):
                                            p(
                                                f"[0..{property.cardinality_max}]",
                                                _class="tableblock",
                                            )
                                        elif (
                                            isinstance(property.cardinality_min, int)
                                            and property.cardinality_max is None
                                        ):
                                            p(
                                                f"[{property.cardinality_min}..*]",
                                                _class="tableblock",
                                            )
                                        elif (
                                            property.cardinality_min
                                            == property.cardinality_max
                                        ):
                                            p(
                                                f"[{property.cardinality_max}]",
                                                _class="tableblock",
                                            )
                                        else:
                                            p(
                                                f"[{property.cardinality_min}..{property.cardinality_max}]",
                                                _class="tableblock",
                                            )
                                    with td(_class="tableblock halign-left valign-top"):
                                        if property.value_type is not None:
                                            if (
                                                property.value_type.iri
                                                in self.query.class_index
                                            ):
                                                fragment = make_html_fragment(
                                                    CLASS_STRING.format(
                                                        property.value_type.name
                                                    )
                                                )
                                                a(
                                                    property.value_type.name,
                                                    href=f"#{fragment}",
                                                )
                                            else:
                                                external_link(
                                                    property.value_type.name,
                                                    property.value_type.iri,
                                                )

                                    with td(_class="tableblock halign-left valign-top"):
                                        if property.value_class_types:
                                            with p(
                                                _class="tableblock",
                                            ):
                                                for (
                                                    value_class_type
                                                ) in property.value_class_types:
                                                    if (
                                                        value_class_type.iri
                                                        in self.query.class_index
                                                    ):
                                                        fragment = make_html_fragment(
                                                            CLASS_STRING.format(
                                                                value_class_type.name
                                                            )
                                                        )
                                                        a(
                                                            value_class_type.name,
                                                            href=f"#{fragment}",
                                                        )
                                                    else:
                                                        external_link(
                                                            value_class_type.name,
                                                            value_class_type.iri,
                                                        )

            if cls.examples:
                h5("Examples")
                with div(_class="sect5"):
                    for ex in cls.examples:
                        example(ex, 6)

    def _make_component_model_property(self, prop: RDFProperty):
        with div(_class="sect3"):
            h4(ANNOTATION_PROPERTY_STRING.format(prop.name), True)

            with p("IRI:", _class="overflow-x-auto"):
                external_link(prop.iri, href=prop.iri)

            if prop.description:
                with div(_class="paragraph"):
                    p(prop.description)

            if prop.notes:
                for note in prop.notes:
                    with div(_class="admonitionblock note"):
                        with table():
                            with tbody():
                                with tr():
                                    with td(_class="icon"):
                                        div(note.type, _class="title")
                                    td(note.value, _class="content")

            if prop.super_properties:
                p("Sub property of:")
                with ul():
                    for super_property in prop.super_properties:
                        with li():
                            # TODO: Dynamically render internal or external link based on some index.
                            external_link(super_property.name, super_property.iri)

            if prop.domain_includes:
                p("Domain includes:")
                with ul():
                    for domain_include_value in prop.domain_includes:
                        with li():
                            if domain_include_value.iri in self.query.class_index:
                                fragment = make_html_fragment(
                                    CLASS_STRING.format(domain_include_value.name)
                                )
                                a(
                                    domain_include_value.name,
                                    href=f"#{fragment}",
                                )
                            else:
                                external_link(
                                    domain_include_value.name, domain_include_value.iri
                                )

            if prop.range_includes:
                p("Range includes:")
                with ul():
                    for domain_include_value in prop.range_includes:
                        with li():
                            if domain_include_value.iri in self.query.class_index:
                                fragment = make_html_fragment(
                                    CLASS_STRING.format(domain_include_value.name)
                                )
                                a(
                                    domain_include_value.name,
                                    href=f"#{fragment}",
                                )
                            else:
                                external_link(
                                    domain_include_value.name, domain_include_value.iri
                                )

            if prop.is_defined_by is not None:
                with p("Is defined by "):
                    # TODO: determine whether this is determined by local module or external.
                    external_link(prop.is_defined_by.name, href=prop.is_defined_by.iri)

    def _make_component_model_core(self, component_model: ComponentModel):
        with div(_class="sect2"):
            h3("Classes", identifier=f"{component_model.name} - Classes")
            hr()
            for i, cls in enumerate(component_model.classes):
                self._make_component_model_class(cls)

                if i != len(component_model.classes) - 1:
                    hr()

        if component_model.annotation_properties:
            hr()
            with div(_class="sect2"):
                h3(
                    "Annotation Properties",
                    identifier=f"{component_model.name} - Annotation Properties",
                )
                hr()
                for i, prop in enumerate(component_model.annotation_properties):
                    self._make_component_model_property(prop)

                    if i != len(component_model.annotation_properties) - 1:
                        hr()

        if component_model.datatype_properties:
            hr()
            with div(_class="sect2"):
                h3(
                    "Datatype Properties",
                    identifier=f"{component_model.name} - Datatype Properties",
                )
                hr()
                for i, prop in enumerate(component_model.datatype_properties):
                    self._make_component_model_property(prop)

                    if i != len(component_model.datatype_properties) - 1:
                        hr()

        if component_model.object_properties:
            hr()
            with div(_class="sect2"):
                h3(
                    "Object Properties",
                    identifier=f"{component_model.name} - Object Properties",
                )
                hr()
                for i, prop in enumerate(component_model.object_properties):
                    self._make_component_model_property(prop)

                    if i != len(component_model.object_properties) - 1:
                        hr()

        if component_model.ontology_properties:
            hr()
            with div(_class="sect2"):
                h3(
                    "Ontology Properties",
                    identifier=f"{component_model.name} - Ontology Properties",
                )
                hr()
                for i, prop in enumerate(component_model.ontology_properties):
                    self._make_component_model_property(prop)

                    if i != len(component_model.ontology_properties) - 1:
                        hr()

    def _make_component_model(self, component_model: ComponentModel):
        with div(_class="sect1"):
            h2(MODULE_STRING.format(component_model.name), True)
            with div(_class="sect2"):
                with div(_class="paragraph"):
                    with p("IRI:"):
                        external_link(component_model.iri, href=component_model.iri)

                if component_model.description:
                    with div(_class="paragraph"):
                        p(component_model.description)

                if component_model.examples:
                    h3("Examples")
                    with div(_class="sect4"):
                        for ex in component_model.examples:
                            example(ex, 4)

                hr()

                self._make_component_model_core(component_model)

    def _class_has_valid_subclasses(self, cls: Class) -> bool:
        count = 0
        for subcls in cls.subclasses:
            if subcls.iri in self.query.class_index:
                count += 1
        return count != 0

    def _make_class_hierarchy(self, classes: list[Class]):
        with ul(_class="nested-hierarchy-list"):
            for cls in classes:
                with li():
                    span(
                        _class="hierarchy-node"
                        if self._class_has_valid_subclasses(cls)
                        else "hierarchy-node-leaf"
                        if cls.subclasses
                        else "hierarchy-node-leaf"
                    )
                    fragment = make_html_fragment(CLASS_STRING.format(cls.name))
                    a(cls.name, href=f"#{fragment}")
                    if cls.subclasses:
                        self._make_class_hierarchy(cls.subclasses)

    def _make_class_hierarchy_top_level(self):
        component_models = self.query.component_models

        h2("Class Hierarchy", True)
        with div(_class="class-hierarchy"):
            with ul(_class="hierarchy-list"):
                for component_model in component_models:
                    with li():
                        span(_class="hierarchy-node")
                        fragment = make_html_fragment(
                            MODULE_STRING.format(component_model.name)
                        )
                        a(component_model.name, href=f"#{fragment}")
                        if component_model.top_level_classes:
                            self._make_class_hierarchy(
                                component_model.top_level_classes
                            )

        style(
            raw(
                "\n"
                + open(
                    Path(__file__).parent.parent.parent / "static/class-hierarchy.css"
                ).read()
                + "\n\t"
            )
        )
        script(
            raw(
                open(
                    Path(__file__).parent.parent.parent / "static/class-hierarchy.js"
                ).read()
            ),
        )

    def _make_component_models(self):
        with self.content:
            with div(_class="sect1"):
                self._make_class_hierarchy_top_level()

                if len(self.query.component_models) == 1:
                    h2("Classes and Properties")
                    self._make_component_model_core(self.query.component_models[0])
                else:
                    for component_model in self.query.component_models:
                        self._make_component_model(component_model)

    def _make_examples(self):
        with self.content:
            with div(_class="sect1"):
                for ex in self.query.examples:
                    example(ex, 2)

    def _make_preamble(self):
        with self.content:
            with div(id="preamble"):
                with div(_class="sectionbody"):
                    with table(
                        _class="tableblock frame-none grid-none stripes-odd stretch"
                    ):
                        with colgroup():
                            col(_class="w-full")

                        with tbody():
                            if DCTERMS.publisher in self.query.onts_props:
                                with tr(_class="bg-white"):
                                    with td(
                                        _class="tableblock halign-right valign-top"
                                    ):
                                        with p(_class="tableblock"):
                                            strong(
                                                str(
                                                    self.query.onts_props[
                                                        DCTERMS.publisher
                                                    ][0]
                                                ),
                                                _class="big",
                                            )

                            # Modified Date
                            if (
                                DCTERMS.modified in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.modified]) > 0
                            ):
                                metadata_row(
                                    "Modified Date",
                                    str(self.query.onts_props[DCTERMS.modified][0]),
                                )

                            # Submission Date
                            if (
                                DCTERMS.created in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.created]) > 0
                            ):
                                metadata_row(
                                    "Submission Date",
                                    str(self.query.onts_props[DCTERMS.created][0]),
                                )

                            # Approval Date
                            if (
                                DCTERMS.dateAccepted in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.dateAccepted]) > 0
                            ):
                                metadata_row(
                                    "Approval Date",
                                    str(self.query.onts_props[DCTERMS.dateAccepted][0]),
                                )

                            # Publication Date
                            if (
                                DCTERMS.issued in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.issued]) > 0
                            ):
                                metadata_row(
                                    "Publication Date",
                                    str(self.query.onts_props[DCTERMS.issued][0]),
                                )

                            # External identifier of this document
                            metadata_row(
                                "External identifier of this document",
                                str(self.iri),
                                True,
                            )

                            # Internal reference number of this document
                            if (
                                SDO.identifier in self.query.onts_props
                                and len(self.query.onts_props[SDO.identifier]) > 0
                            ):
                                metadata_row(
                                    "Internal reference number of this document",
                                    str(self.query.onts_props[SDO.identifier][0]),
                                )

                            # Version
                            if (
                                OWL.versionInfo in self.query.onts_props
                                and len(self.query.onts_props[OWL.versionInfo]) > 0
                            ):
                                metadata_row(
                                    "Version",
                                    str(self.query.onts_props[OWL.versionInfo][0]),
                                )

                            # Category
                            if (
                                SDO.category in self.query.onts_props
                                and len(self.query.onts_props[SDO.category]) > 0
                            ):
                                categories = [
                                    str(category)
                                    for category in self.query.onts_props[SDO.category]
                                ]
                                metadata_row("Category", categories)

                            # Editors
                            if (
                                DCTERMS.creator in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.creator]) > 0
                            ):
                                editors = [
                                    str(editor)
                                    for editor in self.query.onts_props[DCTERMS.creator]
                                ]
                                metadata_row(
                                    "Editors",
                                    editors,
                                )

                            # Contributors
                            if (
                                DCTERMS.contributor in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.contributor]) > 0
                            ):
                                contributors = [
                                    str(contributor)
                                    for contributor in self.query.onts_props[
                                        DCTERMS.contributor
                                    ]
                                ]
                                metadata_row(
                                    "Contributors",
                                    contributors,
                                )

                            # License
                            if (
                                DCTERMS.license in self.query.onts_props
                                and len(self.query.onts_props[DCTERMS.license]) > 0
                            ):
                                metadata_row(
                                    "License",
                                    str(self.query.onts_props[DCTERMS.license][0]),
                                    True,
                                )

                            # Preferred Namespace Prefix
                            if (
                                VANN.preferredNamespacePrefix in self.query.onts_props
                                and len(
                                    self.query.onts_props[
                                        VANN.preferredNamespacePrefix
                                    ][0]
                                )
                                > 0
                            ):
                                metadata_row(
                                    "Preferred Namespace Prefix",
                                    str(
                                        self.query.onts_props[
                                            VANN.preferredNamespacePrefix
                                        ][0]
                                    ),
                                )

                if (
                    DCTERMS.description in self.query.onts_props
                    and len(self.query.onts_props[DCTERMS.description]) > 0
                ):
                    p(self.query.onts_props[DCTERMS.description])

                if (
                    SKOS.historyNote in self.query.onts_props
                    and len(self.query.onts_props[SKOS.historyNote]) > 0
                ):
                    p(self.query.onts_props[SKOS.historyNote])

    def _make_head(
        self, schema_org: Graph, include_css: bool = True, destination: Path = None
    ):
        """Healper function for make_html(). Makes <head>???</head> content"""
        with self.doc.head:
            # use standard pyLODE stylesheet
            if include_css:
                style(
                    raw(
                        "\n"
                        + open(
                            Path(__file__).parent.parent.parent / "static/asciidoc.css"
                        ).read()
                        + "\n\t"
                    )
                )
                style(
                    raw(
                        "\n"
                        + open(
                            Path(__file__).parent.parent.parent / "static/pylode.css"
                        ).read()
                        + "\n\t"
                    )
                )
            else:
                link(href="pylode.css", rel="stylesheet", type="text/css")
                shutil.copy(
                    Path(__file__).parent.parent / "pylode.css",
                    destination.parent / "pylode.css",
                )
            link(
                rel="stylesheet",
                href="https://fonts.googleapis.com/css?family=Open+Sans:300,300italic,400,400italic,600,600italic%7CNoto+Serif:400,400italic,700,700italic%7CDroid+Sans+Mono:400,700",
            )
            link(
                rel="stylesheet",
                href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css",
            )
            link(
                rel="icon",
                type="image/png",
                sizes="16x16",
                href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABhklEQVQ4jbWPzStEURjG3yQLirlGKUnKFO45Z+SjmXvnnmthQcpCoVhYmD/AwmJiI3OvZuZc2U3UlKU0/gAslMw9JgvhHxAr2fko7r0jHSsl+TgbTz2Lt5731/MASEiJW9ONml2QyX6rsGalmnT74v8BDf12hxJfpV8d1uwNKUBYszabdFv84L8B9X0rESVmmUup2fme0cVhJWaZHw4NWL1SewEAfDe6H3Dy6Ll456WEJsRZS630MwCAOI20ei5OBpxse5zcBZw8eS4uPpfIuDiCainIg9umBCU0GZzgLZ9Hn31OgoATL+CkLDGB5H1OKj4nFd/FBxUXJ0UZNb4edw/6nLyJXaj5FeCVyPLNIVmYK8TG1IwWb16L1gEACAFV90ftoT8bdOX0EeyY99gxBXZMgRz6qGb1KantAACI0UvE6F5XJqEjpsdURouI0Vt5gGOUkUNnPu7ObGIIMfNaGqDmjDRi9FZldF1lRgYzeqUyeoiY4ag5Iy3RgOYRM8+/M2bG8efsO4hGrpmJseyMAAAAAElFTkSuQmCC",
            )
            link(
                rel="icon",
                type="image/png",
                sizes="32x32",
                href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAC40lEQVRYhe2UT0hUQRzHp6Iss1B3VZKIDbbdfW9mnoi4f3zzjkJQeOgS0SEIb1EWBGGlLLu460zQPQM1unUIIjA6rfpm6ZAhHjoIRVQUFUlEbG+euTsdXG1d3VL3bVD4g+9h+L35fT/8fvN7ADgY9aHY5fpIvK82HO9ysu66wxWOzbkjcekKx0a2ALYA/n2AGi3a6ArFezcidziecQygNhhrcUficjP6PwBqtGijKxy/thnVBePHywYoDsFhl53GV8SEcsTx4usCMLUewTVpc23BNvEzm6Neyf1+KcG2vwqwUjgrOJq2JmHftwmkVBRGTvncFodnbI7vChO/FRznCmHsNM7aHM9Yk7Df5iqsLMw9sMNOK2g+jS4IEz0UJv4iuJZb2RltWnB4UZqH6ioGAgAAGe5vtiZhtzDx7OoRadLmeM7m6IRjhnLMW2Vx1bA5GhAmnhIcz6/xNj4Ujsky8UspwfayjDPjsF2Y6L7N8Vzx/BfP+KPg6LbgSqd8DnfJW2CnbaLhfH5ephpqygJYvQU4Z3P82TLRsDDhUTnmrSq+Y3N0Mg+Xldy/zwEAnLMWZ3pHpNExmfLs/t0dOdVcbT0JeKxUwFP2VljjqiE47Jp53LTXNxhsUZjerTByXWX6VZWRs/4bIQ2ACv+UAomgDzLCISNZxAxZKMhIDjLy1JfsaK+I+eGBUBNk5E2x8RogX/PdcDZUqieWTSh5D6nOVKqfhoycUmlHFFIyu5RXqf7AcQDISCpv/tqbMBqK883RtmpISRoxQyJKPgGn3wNk5NEigDFa6hslqV/Kj+FdBQD0bshIDlKSLlVcoWQo36UhR80BAMB73lulMn0EMpJTqD6qJiOt3mho/8GbkT2BZNgDB/V+RI0fkOrT3kRIVQbaDizJm2hdNbINBxwk5xAj3yEjuV9rZ1iIkgxixkLBA83mz8uCjLwoGwAx0vOnFSy5mtR4VTaAQvVORMnwZgSpzkrV/QmdE2tKe46+MQAAAABJRU5ErkJggg==",
            )
            meta(http_equiv="Content-Type", content="text/html; charset=utf-8")
            script(
                raw("\n" + schema_org.serialize(format="json-ld") + "\n\t"),
                type="application/ld+json",
                id="schema.org",
            )
