#!/usr/bin/env python

"""A simple list and dictionary XML translation module."""


class XmlListConfig(list):
    """Specialized treatment of a XML document as a list."""

    def __init__(self, aList):
        super().__init__()
        for element in aList:
            if element:
                # treat like dict
                if len(element) == 1 or element[0].tag != element[1].tag:
                    self.append(XmlDictConfig(element))
                # treat like list
                elif element[0].tag == element[1].tag:
                    self.append(XmlListConfig(element))
            elif element.text:
                text = element.text.strip()
                if text:
                    self.append(text)


class XmlDictConfig(dict):
    """Specialized treatment of a XML document as a dictionary.

    Example usage:

    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)

    Or, if you want to use an XML string:

    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)

    And then use xmldict for what it is... a dict.
    """

    def __init__(self, parent_element):
        super().__init__()
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # Treat like dict - assume that if the first two tags in a
                # series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    a_dict = XmlDictConfig(element)
                # Treat like list - we assume that if the first two tags in a
                # series are the same, then the rest are the same.
                else:
                    # Here, the list is put in a dictionary; the key is the tag
                    # name the list elements all share in common, and the value
                    # is the list itself.
                    a_dict = {element[0].tag: XmlListConfig(element)}
                # If the tag has attributes, add those to the dict
                if element.items():
                    a_dict.update(dict(element.items()))
                self.update({element.tag: a_dict})
            # This assumes that there will be no text in the object if the tag
            # has an attribute. This may or may not be a good idea.
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # Extract the text if there are no child tags and no attributes.
            else:
                self.update({element.tag: element.text})
