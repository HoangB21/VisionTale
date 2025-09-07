import logging
import os
import json
import asyncio
from server.config.config import load_config
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import deque
from .base_service import SingletonService
from langchain_core.tools import tool, StructuredTool

logger = logging.getLogger(__name__)


class KGService(SingletonService):
    def _initialize(self):
        self.kg_cache = {}  # Cache for loaded knowledge graphs
        self.kg_dirty = {}  # Tracks modified cache
        self.config = load_config()
        self.tools = []
        self._register_tools()

    def _register_tools(self):
        def inquire_entities(project_name: str, names: List[str]) -> str:
            """Query entity information for single or multiple entities"""
            try:
                result = self.inquire_entities(project_name, names)
                return result
            except Exception as e:
                logger.error(
                    f"KGService.mcp_tool.inquire_entities: Error: {str(e)}", exc_info=True)
                return json.dumps({"error": f"Error in inquire_entities: {str(e)}"})

        def new_entity(project_name: str, name: str, attributes: Optional[dict] = None) -> str:
            """Add a new entity"""
            try:
                result = self.new_entity(project_name, name, attributes)
                logger.info(
                    f"KGService.mcp_tool.new_entity: Returned: {result}")
                return result
            except Exception as e:
                logger.error(
                    f"KGService.mcp_tool.new_entity: Error: {str(e)}", exc_info=True)
                return json.dumps({"error": f"Error in new_entity: {str(e)}"})

        def modify_entity(project_name: str, name: str, attributes: Optional[dict] = None) -> str:
            """Modify an entity"""
            return self.modify_entity(project_name, name, attributes)

        def delete_entity(project_name: str, name: str) -> str:
            """Delete an entity"""
            return self.delete_entity(project_name, name)

        def inquire_relationship(project_name: str, entity_a: str, entity_b: str) -> str:
            """Query relationship between two entities"""
            return self.inquire_relationship(project_name, entity_a, entity_b)

        def new_relationship(project_name: str, type: str, source: str, target: str, attributes: Optional[dict] = None) -> str:
            """Add a new relationship"""
            return self.new_relationship(project_name, type, source, target, attributes)

        def modify_relationship(project_name: str, type: str, source: str, target: str, attributes: Optional[dict] = None) -> str:
            """Modify a relationship"""
            return self.modify_relationship(project_name, type, source, target, attributes)

        def delete_relationship(project_name: str, type: str, source: str, target: str) -> str:
            """Delete a relationship"""
            return self.delete_relationship(project_name, type, source, target)

        def inquire_entity_relationships(project_name: str, name: str) -> str:
            """Query all relationships of an entity"""
            return self.inquire_entity_relationships(project_name, name)

        def inquire_entity_names(project_name: str) -> str:
            """Get list of all entity names"""
            logger.info(
                f"KGService.mcp_tool.inquire_entity_names: Called with project_name='{project_name}'")
            try:
                result_list = self.inquire_entity_names(project_name)
                logger.info(
                    f"KGService.mcp_tool.inquire_entity_names: Returned: {result_list}")
                return json.dumps(result_list)
            except Exception as e:
                logger.error(
                    f"KGService.mcp_tool.inquire_entity_names: Error: {str(e)}", exc_info=True)
                return json.dumps({"error": f"Error in inquire_entity_names: {str(e)}", "names": []})

        def inquire_entity_list(project_name: str) -> str:
            """Get list of all entities with full information"""
            return self.inquire_entity_list(project_name)

        def get_locked_project_entities(project_name: str) -> str:
            """Get list of locked entities in a project"""
            logger.info(
                f"KGService.mcp_tool.get_locked_project_entities: Called with project_name='{project_name}'")
            try:
                result_list = self.get_locked_entities(project_name)
                logger.info(
                    f"KGService.mcp_tool.get_locked_project_entities: Returned: {result_list}")
                return json.dumps(result_list)
            except Exception as e:
                logger.error(
                    f"KGService.mcp_tool.get_locked_project_entities: Error: {str(e)}", exc_info=True)
                return json.dumps({"error": f"Error in get_locked_project_entities: {str(e)}", "locked_entities": []})

        self.tools = [
            StructuredTool.from_function(func=inquire_entities),
            StructuredTool.from_function(func=new_entity),
            StructuredTool.from_function(func=modify_entity),
            StructuredTool.from_function(func=delete_entity),
            StructuredTool.from_function(func=inquire_relationship),
            StructuredTool.from_function(func=new_relationship),
            StructuredTool.from_function(func=modify_relationship),
            StructuredTool.from_function(func=delete_relationship),
            StructuredTool.from_function(func=inquire_entity_relationships),
            StructuredTool.from_function(func=inquire_entity_names),
            StructuredTool.from_function(func=inquire_entity_list),
            StructuredTool.from_function(func=get_locked_project_entities)
        ]

    def _get_kg_path(self, project_name: str) -> str:
        return os.path.join(self.config['projects_path'], project_name, 'kg.json')

    def _load_kg(self, project_name: str) -> dict:
        """
        Load project knowledge graph

        Args:
            project_name (str): Project ID

        Returns:
            dict: Knowledge graph data

        Raises:
            ValueError: If knowledge graph file format is invalid
            Exception: For other loading errors
        """
        if project_name in self.kg_cache:
            return self.kg_cache[project_name]

        kg_path = self._get_kg_path(project_name)
        default_kg = {'entities': [],
                      'relationships': [], 'locked_entities': []}

        if not os.path.exists(kg_path):
            self.kg_cache[project_name] = default_kg
            return default_kg

        try:
            with open(kg_path, 'r', encoding='utf-8') as f:
                kg_data = json.load(f)

                if not isinstance(kg_data, dict):
                    raise ValueError(
                        'Knowledge graph data must be a dictionary')

                kg_data.setdefault('entities', [])
                kg_data.setdefault('relationships', [])
                kg_data.setdefault('locked_entities', [])

                if not isinstance(kg_data['entities'], list):
                    raise ValueError('Entities must be a list')
                if not isinstance(kg_data['relationships'], list):
                    raise ValueError('Relationships must be a list')
                if not isinstance(kg_data['locked_entities'], list):
                    raise ValueError('Locked_entities must be a list')

                self.kg_cache[project_name] = kg_data
                return kg_data
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid knowledge graph file format: {str(e)}')
        except Exception as e:
            raise Exception(f'Error loading knowledge graph: {str(e)}')

    def save_kg(self, project_name: str) -> None:
        """
        Save knowledge graph to file

        Args:
            project_name (str): Project ID
        """
        if project_name not in self.kg_cache:
            raise Exception(
                f"Knowledge graph for project {project_name} not loaded")

        kg_path = self._get_kg_path(project_name)
        os.makedirs(os.path.dirname(kg_path), exist_ok=True)
        kg_data = self._load_kg(project_name)
        try:
            with open(kg_path, 'w', encoding='utf-8') as f:
                json.dump(kg_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f'Error saving knowledge graph: {str(e)}')

    def get_tools(self, include_all: bool = False) -> List[dict]:
        """
        Get list of knowledge graph tools

        Args:
            include_all (bool): Whether to include all tools (default: False)

        Returns:
            List[dict]: List of tools
        """
        return self.tools

    def inquire_entities(self, project_name: str, names: List[str]) -> str:
        """
        Query entity information for single or multiple entities

        Args:
            project_name (str): Project ID
            names (List[str]): List of entity names

        Returns:
            str: JSON string of entity information list.
                 If querying a single entity and not found, returns error string.
                 If querying multiple entities, returns found entities, ignoring not found.
        """
        try:
            kg_data = self._load_kg(project_name)
            entities = [entity for entity in kg_data.get(
                'entities', []) if entity['name'] in names]

            if len(names) == 1 and not entities:
                return f"Entity {names[0]} does not exist"

            return json.dumps(entities, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Failed to query entities: {str(e)}")

    def new_entity(self, project_name: str, name: str, attributes: Optional[dict] = None, save_kg: bool = True) -> str:
        """
        Add a new entity

        Args:
            project_name (str): Project ID
            name (str): Entity name
            attributes (Optional[dict]): Entity attributes
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        kg_data = self._load_kg(project_name)

        if any(e['name'] == name for e in kg_data['entities']):
            return f"Entity {name} already exists"

        entity = {'name': name, 'attributes': attributes or {}}
        kg_data['entities'].append(entity)
        self.kg_cache[project_name] = kg_data

        if save_kg:
            self.save_kg(project_name)

        return "Added successfully"

    def modify_entity(self, project_name: str, name: str, attributes: Optional[dict] = None, save_kg: bool = True) -> str:
        """
        Modify an entity

        Args:
            project_name (str): Project ID
            name (str): Entity name
            attributes (Optional[dict]): New entity attributes
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        kg_data = self._load_kg(project_name)

        for entity in kg_data['entities']:
            if entity['name'] == name:
                entity['attributes'] = attributes or {}
                self.kg_cache[project_name] = kg_data
                if save_kg:
                    self.save_kg(project_name)
                return "Modified successfully"

        return f"Entity {name} does not exist"

    def delete_entity(self, project_name: str, name: str, save_kg: bool = True) -> str:
        """
        Delete an entity

        Args:
            project_name (str): Project ID
            name (str): Entity name
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        try:
            kg_data = self._load_kg(project_name)

            if name in self.get_locked_entities(project_name):
                return f"Entity {name} is locked and cannot be deleted"

            kg_data['entities'] = [
                e for e in kg_data['entities'] if e['name'] != name]
            kg_data['relationships'] = [r for r in kg_data['relationships']
                                        if r['source'] != name and r['target'] != name]

            self.kg_cache[project_name] = kg_data
            if save_kg:
                self.save_kg(project_name)

            return "Deleted successfully"
        except Exception as e:
            raise Exception(f"Failed to delete entity: {str(e)}")

    def inquire_relationship(self, project_name: str, entity_a: str, entity_b: str) -> str:
        """
        Query relationship between two entities

        Args:
            project_name (str): Project ID
            entity_a (str): First entity name
            entity_b (str): Second entity name

        Returns:
            str: Relationship information
        """
        kg_data = self._load_kg(project_name)
        direct = [r for r in kg_data['relationships'] if (r['source'] == entity_a and r['target'] == entity_b) or (
            r['source'] == entity_b and r['target'] == entity_a)]

        if direct:
            return json.dumps(direct, ensure_ascii=False)

        graph = self._build_graph(kg_data)
        path = self._find_shortest_path(graph, entity_a, entity_b)

        if path:
            return f"Found indirect relationship path: {json.dumps(path, ensure_ascii=False)}"

        return "Relationship does not exist"

    def new_relationship(self, project_name: str, type: str, source: str, target: str, attributes: Optional[dict] = None, save_kg: bool = True) -> str:
        """
        Add a new relationship

        Args:
            project_name (str): Project ID
            type (str): Relationship type
            source (str): Source entity name
            target (str): Target entity name
            attributes (Optional[dict]): Relationship attributes
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        try:
            if not type or not type.strip():
                return "Relationship type cannot be empty"

            kg_data = self._load_kg(project_name)

            if not any(e['name'] == source for e in kg_data['entities']):
                return f"Source entity {source} does not exist"
            if not any(e['name'] == target for e in kg_data['entities']):
                return f"Target entity {target} does not exist"

            if any(r['type'] == type and r['source'] == source and r['target'] == target for r in kg_data['relationships']):
                return "Relationship already exists"

            relationship = {
                'type': type,
                'source': source,
                'target': target,
                'attributes': attributes or {}
            }
            kg_data['relationships'].append(relationship)
            self.kg_cache[project_name] = kg_data

            if save_kg:
                self.save_kg(project_name)

            return "Added successfully"
        except Exception as e:
            return f"Error adding relationship: {str(e)}"

    def modify_relationship(self, project_name: str, type: str, source: str, target: str, attributes: Optional[dict] = None, save_kg: bool = True) -> str:
        """
        Modify a relationship

        Args:
            project_name (str): Project ID
            type (str): Relationship type
            source (str): Source entity name
            target (str): Target entity name
            attributes (Optional[dict]): New relationship attributes
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        kg_data = self._load_kg(project_name)

        for rel in kg_data['relationships']:
            if rel['source'] == source and rel['target'] == target:
                rel['type'] = type
                rel['attributes'] = attributes or {}
                self.kg_cache[project_name] = kg_data
                if save_kg:
                    self.save_kg(project_name)
                return "Modified successfully"

        return "Relationship does not exist"

    def delete_relationship(self, project_name: str, type: str, source: str, target: str, save_kg: bool = True) -> str:
        """
        Delete a relationship

        Args:
            project_name (str): Project ID
            type (str): Relationship type
            source (str): Source entity name
            target (str): Target entity name
            save_kg (bool): Whether to save knowledge graph (default: True)

        Returns:
            str: Operation result
        """
        kg_data = self._load_kg(project_name)
        initial_length = len(kg_data['relationships'])
        kg_data['relationships'] = [r for r in kg_data['relationships'] if not (
            r['type'] == type and r['source'] == source and r['target'] == target)]

        if len(kg_data['relationships']) < initial_length:
            self.kg_cache[project_name] = kg_data
            if save_kg:
                self.save_kg(project_name)
            return "Deleted successfully"

        return "Relationship does not exist"

    def inquire_entity_relationships(self, project_name: str, name: str) -> str:
        """
        Query all relationships of an entity

        Args:
            project_name (str): Project ID
            name (str): Entity name

        Returns:
            str: Relationship information
        """
        try:
            kg_data = self._load_kg(project_name)

            if not any(e['name'] == name for e in kg_data['entities']):
                return f"Entity {name} does not exist"

            relationships = [r for r in kg_data['relationships']
                             if r['source'] == name or r['target'] == name]
            return json.dumps(relationships, ensure_ascii=False)
        except Exception as e:
            return f"Error querying entity relationships: {str(e)}"

    def inquire_entity_names(self, project_name: str) -> List[str]:
        """
        Get list of all entity names

        Args:
            project_name (str): Project ID

        Returns:
            List[str]: List of entity names
        """
        kg_data = self._load_kg(project_name)
        return [entity['name'] for entity in kg_data.get('entities', [])]

    def inquire_entity_list(self, project_name: str) -> str:
        """
        Get list of all entities with full information

        Args:
            project_name (str): Project ID

        Returns:
            str: JSON string of entity list with full information
        """
        try:
            kg_data = self._load_kg(project_name)
            entities = kg_data.get('entities', [])
            return json.dumps(entities, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Failed to get entity list: {str(e)}")

    def _build_graph(self, kg_data: dict) -> dict:
        """
        Build graph structure

        Args:
            kg_data (dict): Knowledge graph data

        Returns:
            dict: Graph structure
        """
        graph = {}
        for rel in kg_data['relationships']:
            source, target = rel['source'], rel['target']
            if source not in graph:
                graph[source] = []
            if target not in graph:
                graph[target] = []
            graph[source].append((target, rel))
            graph[target].append((source, rel))
        return graph

    def _find_shortest_path(self, graph: dict, start: str, end: str) -> List[dict]:
        """
        Find shortest path using BFS

        Args:
            graph (dict): Graph structure
            start (str): Starting entity name
            end (str): Target entity name

        Returns:
            List[dict]: Shortest path
        """
        if start not in graph or end not in graph:
            return []

        visited = {start}
        queue = deque([(start, [])])

        while queue:
            current, path = queue.popleft()
            if current == end:
                return path

            for neighbor, rel in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [rel]))
        return []

    def get_locked_entities(self, project_name: str) -> List[str]:
        """
        Get list of locked entities in a project

        Args:
            project_name (str): Project name

        Returns:
            List[str]: List of locked entity names
        """
        kg_data = self._load_kg(project_name)
        return kg_data.get('locked_entities', [])

    def toggle_entity_lock(self, project_name: str, entity_name: str, save_kg: bool = False) -> bool:
        """
        Toggle entity lock status

        Args:
            project_name (str): Project name
            entity_name (str): Entity name
            save_kg (bool): Whether to save knowledge graph (default: False)

        Returns:
            bool: True if now locked, False if now unlocked
        """
        try:
            entities = self.inquire_entity_list(project_name)
            entities = json.loads(entities) if isinstance(
                entities, str) else entities
            if not any(entity['name'] == entity_name for entity in entities):
                raise Exception(f"Entity {entity_name} does not exist")

            kg_data = self._load_kg(project_name)
            locked_entities = kg_data.get('locked_entities', [])

            is_locked = False
            if entity_name in locked_entities:
                locked_entities.remove(entity_name)
            else:
                locked_entities.append(entity_name)
                is_locked = True

            kg_data['locked_entities'] = locked_entities
            self.kg_cache[project_name] = kg_data
            if save_kg:
                self.save_kg(project_name)

            return is_locked
        except Exception as e:
            raise Exception(f"Failed to toggle entity lock status: {str(e)}")
