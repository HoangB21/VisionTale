from json_repair import loads as json_repair_loads
from server.services.schemas import (
    SceneExtractionResult,
    TextDescResult,
    PromptKontextList,
    PromptList,
    append_output_schema_to_prompt,
    CharacterExtractionSummary,
)
from typing import Type
from pydantic import BaseModel, ValidationError
import os
import json
import logging
import re
import asyncio
from typing import AsyncGenerator, List, Dict
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler

from server.services.base_service import SingletonService
from server.services.kg_service import KGService
from server.services.scene_service import SceneService

logger = logging.getLogger(__name__)

# Pydantic and structured model


class LLMService(SingletonService):
    """LLM Service Class Refactored with LangChain"""

    _prompt_cache: Dict[str, str] = {}

    def _initialize(self):
        self.api_key = self.config['llm']['api_key']
        self.api_url = self.config['llm']['api_url']
        self.model_name = self.config['llm']['model_name']

        self.prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'prompts')
        self.projects_path = self.config.get('projects_path', 'projects/')
        self.kg_service = KGService()
        self.scene_service = SceneService()
        # Parse retries: allow override in config.llm.parse_retries, default 2
        self.parse_retries = int(self.config.get(
            'llm', {}).get('parse_retries', 2) or 2)

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,  # e.g., "gemini-1.5-pro"
            google_api_key=self.api_key,
            temperature=0.5,
            max_output_tokens=2048,  # Equivalent to max_output_tokens in genai
        )

        self.agent = initialize_agent(
            tools=[],
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,

        )

    # Structured output tool
    async def _ainvoke_and_parse(self, system_prompt: str, user_content: str, model_type: Type[BaseModel], retries: int = 2) -> BaseModel:
        """Call LLM and parse output into specified Pydantic model, with limited retries and JSON repair."""
        if retries is None:
            retries = self.parse_retries
        attempt = 0
        last_err: Exception | None = None
        while attempt <= retries:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content)
            ]
            response = await self.llm.ainvoke(messages)
            raw = response.content if hasattr(
                response, 'content') else str(response)
            try:
                data = json_repair_loads(raw)
                return model_type.model_validate(data)
            except (ValidationError, Exception) as e:
                last_err = e
                logger.warning(
                    f"Structured parsing failed, attempt {attempt+1}: {e}")
                attempt += 1
                # Moderate backoff
                if attempt <= retries:
                    await asyncio.sleep(0.3 * attempt)
        # Final failure
        if last_err:
            logger.error(f"Structured parsing ultimately failed: {last_err}")
            raise last_err
        raise RuntimeError("Unknown error in structured parsing")

    def _build_system_prompt_with_schema(self, template_name: str, replacements: Dict[str, str], schema_model: Type[BaseModel]) -> str:
        """Load template, replace variables, and append Schema."""
        tpl = self._load_prompt(template_name)
        for k, v in replacements.items():
            tpl = tpl.replace(k, v)
        return append_output_schema_to_prompt(tpl, schema_model)

    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt template"""
        if prompt_file in self._prompt_cache:
            return self._prompt_cache[prompt_file]

        prompt_path = os.path.join(self.prompts_dir, prompt_file)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(
                f'Prompt template does not exist: {prompt_file}')

        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read()

        self._prompt_cache[prompt_file] = prompt
        return prompt

    def _create_agent_executor(self, tools: List[Tool] = None):
        """Create Agent executor"""
        if tools is None or len(tools) == 0:
            return self.agent

        agent = initialize_agent(
            tools=tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,  # Whether to print detailed logs
            handle_parsing_errors=True,

        )

        return agent

    async def _process_text_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Process text stream"""
        callback = AsyncIteratorCallbackHandler()
        # Use asyncio.create_task to run LLM call, so callback.aiter() can start iterating immediately
        task = asyncio.create_task(
            self.llm.ainvoke(messages, config={"callbacks": [callback]})
        )
        async for token in callback.aiter():
            yield token
        # Ensure LLM call task completes
        await task

    async def split_text_and_generate_prompts(self, project_name: str, text: str) -> List[dict]:
        """Split text and generate descriptions"""
        window_size = self.config['llm'].get('window_size', -1)

        # Preprocess text
        split_pattern = r'(?<=[。！？])\s*'
        sentences = [s.replace('\n', ' ').strip()
                     for s in re.split(split_pattern, text) if s.strip()]
        text = "\n".join(sentences)

        # Scene extraction
        scene_names = self.scene_service.get_scene_names(project_name)
        system_prompt_for_scene = self._build_system_prompt_with_schema(
            "scene_extraction.txt",
            {"{scenes}": ",".join(scene_names)},
            SceneExtractionResult,
        )

        # Use structured call
        scene_result = await self._ainvoke_and_parse(system_prompt_for_scene, f"Project name: {project_name}\n\n{text}", SceneExtractionResult)
        self.scene_service.update_scenes(project_name, scene_result.root)

        # Text description generation (using Pydantic structured output)
        entities_names = self.kg_service.inquire_entity_names(project_name)
        scene_names = self.scene_service.get_scene_names(project_name)
        current_text_desc_prompt = self._build_system_prompt_with_schema(
            "text_desc_prompt.txt",
            {"{scenes}": ",".join(scene_names),
             "{entities}": ",".join(entities_names)},
            TextDescResult,
        )

        # Process text chunks
        text_chunks = [text] if window_size <= 0 else [
            "\n".join(sentences[i:i+window_size])
            for i in range(0, len(sentences), window_size)
        ]

        async def process_chunk_structured(chunk: str):
            try:
                result: TextDescResult = await self._ainvoke_and_parse(current_text_desc_prompt, chunk, TextDescResult)
                return [span.model_dump() for span in result.spans]
            except Exception as e:
                logger.error(
                    f"Structured parsing of text description failed: {e}")
                return []

        results = await asyncio.gather(*[process_chunk_structured(chunk) for chunk in text_chunks])
        return [item for sublist in results for item in sublist]

    async def generate_text(self, prompt: str, project_name: str, last_content: str = '') -> AsyncGenerator[str, None]:
        """Generate text"""
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        system_prompt = self._load_prompt('novel_writing.txt')
        system_prompt = system_prompt.replace('{context}', last_content)
        system_prompt = system_prompt.replace('{requirements}', prompt)

        async for token in self._process_text_stream(self.combine_prompts(system_prompt, prompt)):
            yield token

    async def continue_story(self, original_story: str, project_name: str, last_content: str = '') -> AsyncGenerator[str, None]:
        """Continue story"""
        if not original_story:
            raise ValueError("Story content cannot be empty")

        system_prompt = self._load_prompt('story_continuation.txt')
        system_prompt = system_prompt.replace('{context}', last_content)

        async for token in self._process_text_stream(self.combine_prompts(system_prompt, original_story)):
            yield token

    def combine_prompts(self, system_prompt, text, project_name=""):
        """Combine system prompt and user input"""
        if project_name:
            text = f"Project name: {project_name}\n\n{text}"

        message = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]

        return message

    async def extract_character(self, text: str, project_name: str) -> dict:
        """Extract character information from text"""
        if not text:
            raise ValueError("Text content cannot be empty")

        system_prompt = self._load_prompt('character_extraction.txt')

        # Get existing entities and locked entities
        entities = ",".join(self.kg_service.inquire_entity_names(project_name))
        locked_entities = ",".join(
            self.kg_service.get_locked_entities(project_name))

        # Fill prompt variables
        system_prompt = system_prompt.replace(
            "{{entities}}", json.dumps(entities, ensure_ascii=False))
        system_prompt = system_prompt.replace(
            "{{locked_entities}}", json.dumps(locked_entities, ensure_ascii=False))
        # Append output Schema (summary JSON)
        system_prompt = append_output_schema_to_prompt(
            system_prompt, CharacterExtractionSummary)

        # Create LangChain Agent
        agent = self._create_agent_executor(self.kg_service.get_tools())

        result_text = await agent.ainvoke(self.combine_prompts(system_prompt, text, project_name))
        final_answer = result_text.get('output') if isinstance(
            result_text, dict) else result_text
        # Try parsing summary JSON
        summary = None
        try:
            if isinstance(final_answer, (dict, list)):
                summary = CharacterExtractionSummary.model_validate(
                    final_answer)
            else:
                summary_data = json_repair_loads(str(final_answer))
                summary = CharacterExtractionSummary.model_validate(
                    summary_data)
        except Exception as e:
            logger.warning(f"Parsing character extraction summary failed: {e}")

        # Get results
        entities = json.loads(
            self.kg_service.inquire_entity_list(project_name))
        relationships = {
            entity['name']: json.loads(self.kg_service.inquire_entity_relationships(
                project_name=project_name,
                name=entity['name']
            ))
            for entity in entities if isinstance(entity, dict) and 'name' in entity
        }

        self.kg_service.save_kg(project_name)

        return {
            'result': final_answer,
            'summary': summary.model_dump() if summary else None,
            'entities': entities,
            'relationships': relationships
        }

    async def _translate_prompt_batch(self, project_name: str, prompts: List[str], system_prompt: str, entities: List[dict]) -> List[str]:
        """
        Batch translate prompts
        Args:
            project_name: Project name
            prompts: List of prompts
            system_prompt: System prompt template
            entities: List of entity information
        Returns:
            List of translated prompts
        """
        try:
            # Collect all entity or base scene names in prompts
            all_entity_names = set()
            all_scene_names = set()
            for prompt in prompts:
                entity_names = re.findall(r'\{([^}]+)\}', prompt)
                all_entity_names.update(entity_names)
                scene_names = re.findall(r'\$\$([^$]+)\$\$', prompt)
                all_scene_names.update(scene_names)

            # Find corresponding entity information
            entity_infos = []
            for name in all_entity_names:
                for entity in entities:
                    if entity['name'] == name:
                        info_str = f"{entity['name']}: {entity.get('attributes', {}).get('description', '')}"
                        entity_infos.append(info_str)
                        break

            scene_dict = self.scene_service.get_scene_dict(
                project_name, all_scene_names)
            scene_infos = [
                f"{scene_name}: {scene_dict.get(scene_name, '')}" for scene_name in all_scene_names if scene_dict.get(scene_name, '')]

            # Copy system prompt and replace entity information
            current_system_prompt = system_prompt
            if entity_infos:
                current_system_prompt = current_system_prompt.replace(
                    '{entities}', '\n'.join(entity_infos))
            if scene_infos:
                current_system_prompt = current_system_prompt.replace(
                    '{scenes}', '\n'.join(scene_infos))
            # Append Schema: normal translation path outputs numbered English lines, but use array format to avoid parsing ambiguity
            current_system_prompt = append_output_schema_to_prompt(
                current_system_prompt, PromptList)

            # Split prompts into smaller batches
            batch_size = 4
            translated_prompts = []
            total_batches = (len(prompts) + batch_size - 1) // batch_size

            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(prompts))
                batch_prompts = prompts[start_idx:end_idx]

                # Build numbered prompt list (as user content)
                numbered_prompts = []
                for i, prompt in enumerate(batch_prompts, start_idx + 1):
                    numbered_prompts.append(f"{i}. {prompt}")
                prompts_str = '\n'.join(
                    numbered_prompts) + f"\n\nReturn exactly {len(batch_prompts)} items in the array, one per input line, no extra or missing."

                logging.info(
                    f"Processing batch {batch_index + 1}/{total_batches} of prompts, containing {len(batch_prompts)} prompts")
                logging.info(f"Current numbered prompt list:\n{prompts_str}")

                # Parse once, retry if necessary
                attempt = 0
                while True:
                    result_model: PromptList = await self._ainvoke_and_parse(current_system_prompt, prompts_str, PromptList, retries=self.parse_retries)
                    batch_results = list(result_model.root)
                    if len(batch_results) == len(batch_prompts):
                        break
                    attempt += 1
                    if attempt > 1:
                        raise Exception(
                            f"Batch {batch_index + 1} translation result count ({len(batch_results)}) does not match input count ({len(batch_prompts)})")
                    prompts_str = '\n'.join(
                        numbered_prompts) + f"\n\nIMPORTANT: Output MUST be a JSON array of {len(batch_prompts)} strings."

                translated_prompts.extend(batch_results)

                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)

            if len(translated_prompts) != len(prompts):
                raise Exception(
                    f"Total translation result count ({len(translated_prompts)}) does not match input count ({len(prompts)})")

            return translated_prompts

        except Exception as e:
            logging.error(f'Batch translation of prompts failed: {str(e)}')
            raise

    async def _translate_prompt_batch_reference_image(self, project_name: str, prompts: List[str], system_prompt: str, entities: List[dict]) -> List[str]:
        """
        Batch translate prompts
        Args:
            project_name: Project name
            prompts: List of prompts
            system_prompt: System prompt template
            entities: List of entity information
        Returns:
            List of translated prompts
        """
        try:
            # Find corresponding entity information
            entity_infos = {}
            for entity in entities:
                info_str = entity.get('attributes', {}).get('description', '')
                info_str_list = info_str.split(",")
                info_str = info_str_list[0]

                entity_infos[entity['name']] = info_str

            scene_infos = self.scene_service.load_scenes(project_name)
            for scene_name, des in scene_infos.items():
                des_list = des.split(",")
                scene_infos[scene_name] = des_list[0]

            # Replace entity markers in each prompt
            processed_prompts = []
            for prompt in prompts:
                entity_names = re.findall(r'\{([^}]+)\}', prompt)
                scene_names = re.findall(r'\[([^$]+)\]', prompt)
                processed_prompt = prompt
                for name in entity_names:
                    if name in entity_infos:
                        n = "{"+name+"}"
                        new_n = f"{name}[{entity_infos[name]}]"
                        processed_prompt = processed_prompt.replace(n, new_n)

                for scene_name in scene_names:
                    if scene_name in scene_infos:
                        n = "["+scene_name+"]"
                        new_n = f"{scene_name}[{scene_infos[scene_name]}]"
                        processed_prompt = processed_prompt.replace(n, new_n)

                processed_prompts.append(processed_prompt)

            # Copy system prompt
            current_system_prompt = system_prompt
            # Append Schema: Kontext output is an array of objects
            current_system_prompt = append_output_schema_to_prompt(
                current_system_prompt, PromptKontextList)

            # Split prompts into smaller batches
            batch_size = 4
            translated_prompts = []
            total_batches = (len(processed_prompts) +
                             batch_size - 1) // batch_size

            for batch_index in range(total_batches):
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(processed_prompts))
                batch_prompts = processed_prompts[start_idx:end_idx]

                # Build numbered prompt list
                numbered_prompts = []
                for i, prompt in enumerate(batch_prompts, start_idx + 1):
                    numbered_prompts.append(f"{i}. {prompt}")
                prompts_str = '\n'.join(
                    numbered_prompts) + f"\n\nReturn exactly {len(batch_prompts)} items, one per input line."

                logging.info(
                    f"Processing batch {batch_index + 1}/{total_batches} of prompts, containing {len(batch_prompts)} prompts")
                logging.info(f"Current numbered prompt list:\n{prompts_str}")

                # Parse once, retry if necessary
                attempt = 0
                while True:
                    result_model: PromptKontextList = await self._ainvoke_and_parse(current_system_prompt, prompts_str, PromptKontextList, retries=self.parse_retries)
                    batch_results = [item.answer for item in result_model.root]
                    if len(batch_results) == len(batch_prompts):
                        break
                    attempt += 1
                    if attempt > 1:
                        raise Exception(
                            f"Batch {batch_index + 1} translation result count ({len(batch_results)}) does not match input count ({len(batch_prompts)})")
                    prompts_str = '\n'.join(
                        numbered_prompts) + f"\n\nIMPORTANT: Output MUST be a JSON array of {len(batch_prompts)} objects with id/convert_entity/thinking/answer."

                translated_prompts.extend(batch_results)

                if batch_index < total_batches - 1:
                    await asyncio.sleep(0.5)

            if len(translated_prompts) != len(prompts):
                raise Exception(
                    f"Total translation result count ({len(translated_prompts)}) does not match input count ({len(prompts)})")

            return translated_prompts

        except Exception as e:
            logging.error(f'Batch translation of prompts failed: {str(e)}')
            raise

    async def translate_prompt(self, project_name: str, prompts: List[str]) -> List[str]:
        """
        Translate prompt list
        Args:
            project_name: Project name
            prompts: List of prompts
        Returns:
            List of translated prompts
        """
        try:
            reference_image_mode = self.config['comfyui'].get(
                'reference_image_mode', True)

            if reference_image_mode:
                system_prompt = self._load_prompt(
                    'prompt_translation_kontext.txt')
            else:
                system_prompt = self._load_prompt('prompt_translation.txt')

            # Get all entity information from knowledge graph
            entities_json = self.kg_service.inquire_entity_list(project_name)
            entities = json.loads(entities_json)

            # Split prompt list into groups
            batch_size = 8
            batches = [prompts[i:i + batch_size]
                       for i in range(0, len(prompts), batch_size)]

            # Process each batch in parallel
            tasks = []
            for batch in batches:
                if reference_image_mode:
                    tasks.append(self._translate_prompt_batch_reference_image(
                        project_name, batch, system_prompt, entities))
                else:
                    tasks.append(self._translate_prompt_batch(
                        project_name, batch, system_prompt, entities))

            # Execute all tasks
            results = await asyncio.gather(*tasks)

            # Merge results from all batches
            translated_prompts = []
            for batch_result in results:
                translated_prompts.extend(batch_result)

            return translated_prompts

        except Exception as e:
            logging.error(f'Translation of prompts failed: {str(e)}')
            raise

    async def split_story_into_chapters(self, story_content: str) -> List[str]:
        """Split story into chapters using LLM, each <= 200 words"""
        prompt_template = self._load_prompt('story_split.txt')
        prompt = prompt_template.replace('{story_content}', story_content)

        # Định nghĩa schema cho kết quả (thêm vào schemas.py nếu chưa có)
        # Giả sử đã thêm vào schemas.py
        from server.services.schemas import StorySplitResult

        system_prompt = self._build_system_prompt_with_schema(
            'story_split.txt',
            {'{story_content}': story_content},
            StorySplitResult
        )

        # Gọi LLM và parse
        result = await self._ainvoke_and_parse(
            system_prompt,
            story_content,
            StorySplitResult
        )

        # Trả về list các chapter content
        return [chapter.content for chapter in result.chapters]
