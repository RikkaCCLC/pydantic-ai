import json
from typing import Annotated

import pytest
from inline_snapshot import snapshot
from pydantic import BaseModel, Field
from pydantic_core import PydanticSerializationError

from pydantic_ai import Agent, RunContext, Tool, UserError
from pydantic_ai.messages import Message, ModelAnyResponse, ModelTextResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel


def test_tool_no_ctx():
    agent = Agent(TestModel())

    with pytest.raises(UserError) as exc_info:

        @agent.tool  # pyright: ignore[reportArgumentType]
        def invalid_tool(x: int) -> str:  # pragma: no cover
            return 'Hello'

    assert str(exc_info.value) == snapshot(
        'Error generating schema for test_tool_no_ctx.<locals>.invalid_tool:\n'
        '  First parameter of tools that take context must be annotated with RunContext[...]'
    )


def test_tool_plain_with_ctx():
    agent = Agent(TestModel())

    with pytest.raises(UserError) as exc_info:

        @agent.tool_plain
        async def invalid_tool(ctx: RunContext[None]) -> str:  # pragma: no cover
            return 'Hello'

    assert str(exc_info.value) == snapshot(
        'Error generating schema for test_tool_plain_with_ctx.<locals>.invalid_tool:\n'
        '  RunContext annotations can only be used with tools that take context'
    )


def test_tool_ctx_second():
    agent = Agent(TestModel())

    with pytest.raises(UserError) as exc_info:

        @agent.tool  # pyright: ignore[reportArgumentType]
        def invalid_tool(x: int, ctx: RunContext[None]) -> str:  # pragma: no cover
            return 'Hello'

    assert str(exc_info.value) == snapshot(
        'Error generating schema for test_tool_ctx_second.<locals>.invalid_tool:\n'
        '  First parameter of tools that take context must be annotated with RunContext[...]\n'
        '  RunContext annotations can only be used as the first argument'
    )


async def google_style_docstring(foo: int, bar: str) -> str:  # pragma: no cover
    """Do foobar stuff, a lot.

    Args:
        foo: The foo thing.
        bar: The bar thing.
    """
    return f'{foo} {bar}'


async def get_json_schema(_messages: list[Message], info: AgentInfo) -> ModelAnyResponse:
    assert len(info.function_tools) == 1
    r = next(iter(info.function_tools.values()))
    return ModelTextResponse(json.dumps(r.json_schema))


def test_docstring_google(set_event_loop: None):
    agent = Agent(FunctionModel(get_json_schema))
    agent.tool_plain(google_style_docstring)

    result = agent.run_sync('Hello')
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'description': 'Do foobar stuff, a lot.',
            'additionalProperties': False,
            'properties': {
                'foo': {'description': 'The foo thing.', 'title': 'Foo', 'type': 'integer'},
                'bar': {'description': 'The bar thing.', 'title': 'Bar', 'type': 'string'},
            },
            'required': ['foo', 'bar'],
            'type': 'object',
        }
    )
    # description should be the first key
    assert next(iter(json_schema)) == 'description'


def sphinx_style_docstring(foo: int, /) -> str:  # pragma: no cover
    """Sphinx style docstring.

    :param foo: The foo thing.
    :return: The result.
    """
    return str(foo)


def test_docstring_sphinx(set_event_loop: None):
    agent = Agent(FunctionModel(get_json_schema))
    agent.tool_plain(sphinx_style_docstring)

    result = agent.run_sync('Hello')
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'description': 'Sphinx style docstring.',
            'additionalProperties': False,
            'properties': {
                'foo': {'description': 'The foo thing.', 'title': 'Foo', 'type': 'integer'},
            },
            'required': ['foo'],
            'type': 'object',
        }
    )


def numpy_style_docstring(*, foo: int, bar: str) -> str:  # pragma: no cover
    """Numpy style docstring.

    Parameters
    ----------
    foo : int
        The foo thing.
    bar : str
        The bar thing.
    """
    return f'{foo} {bar}'


def test_docstring_numpy(set_event_loop: None):
    agent = Agent(FunctionModel(get_json_schema))
    agent.tool_plain(numpy_style_docstring)

    result = agent.run_sync('Hello')
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'description': 'Numpy style docstring.',
            'additionalProperties': False,
            'properties': {
                'foo': {'description': 'The foo thing.', 'title': 'Foo', 'type': 'integer'},
                'bar': {'description': 'The bar thing.', 'title': 'Bar', 'type': 'string'},
            },
            'required': ['foo', 'bar'],
            'type': 'object',
        }
    )


def unknown_docstring(**kwargs: int) -> str:  # pragma: no cover
    """Unknown style docstring."""
    return str(kwargs)


def test_docstring_unknown(set_event_loop: None):
    agent = Agent(FunctionModel(get_json_schema))
    agent.tool_plain(unknown_docstring)

    result = agent.run_sync('Hello')
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'description': 'Unknown style docstring.',
            'additionalProperties': True,
            'properties': {},
            'type': 'object',
        }
    )


# fmt: off
async def google_style_docstring_no_body(
    foo: int, bar: Annotated[str, Field(description='from fields')]
) -> str:  # pragma: no cover
    """
    Args:
        foo: The foo thing.
        bar: The bar thing.
    """
    # fmt: on
    return f'{foo} {bar}'


def test_docstring_google_no_body(set_event_loop: None):
    agent = Agent(FunctionModel(get_json_schema))
    agent.tool_plain(google_style_docstring_no_body)

    result = agent.run_sync('')
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'additionalProperties': False,
            'properties': {
                'foo': {'description': 'The foo thing.', 'title': 'Foo', 'type': 'integer'},
                'bar': {'description': 'from fields', 'title': 'Bar', 'type': 'string'},
            },
            'required': ['foo', 'bar'],
            'type': 'object',
        }
    )


class Foo(BaseModel):
    x: int
    y: str


def test_takes_just_model(set_event_loop: None):
    agent = Agent()


    @agent.tool_plain
    def takes_just_model(model: Foo) -> str:
        return f'{model.x} {model.y}'

    result = agent.run_sync('', model=FunctionModel(get_json_schema))
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            'title': 'Foo',
            'properties': {'x': {'title': 'X', 'type': 'integer'}, 'y': {'title': 'Y', 'type': 'string'}},
            'required': ['x', 'y'],
            'type': 'object',
        }
    )

    result = agent.run_sync('', model=TestModel())
    assert result.data == snapshot('{"takes_just_model":"0 a"}')


def test_takes_model_and_int(set_event_loop: None):
    agent = Agent()

    class Foo(BaseModel):
        x: int
        y: str

    @agent.tool_plain
    def takes_just_model(model: Foo, z: int) -> str:
        return f'{model.x} {model.y} {z}'

    result = agent.run_sync('', model=FunctionModel(get_json_schema))
    json_schema = json.loads(result.data)
    assert json_schema == snapshot(
        {
            '$defs': {
                'Foo': {
                    'properties': {
                        'x': {'title': 'X', 'type': 'integer'},
                        'y': {'title': 'Y', 'type': 'string'},
                    },
                    'required': ['x', 'y'],
                    'title': 'Foo',
                    'type': 'object',
                }
            },
            'additionalProperties': False,
            'properties': {
                'model': {'$ref': '#/$defs/Foo'},
                'z': {'title': 'Z', 'type': 'integer'},
            },
            'required': ['model', 'z'],
            'type': 'object',
        }
    )

    result = agent.run_sync('', model=TestModel())
    assert result.data == snapshot('{"takes_just_model":"0 a 0"}')


# pyright: reportPrivateUsage=false
def test_init_tool_plain(set_event_loop: None):
    call_args: list[int] = []

    def plain_tool(x: int) -> int:
        call_args.append(x)
        return x + 1

    agent = Agent('test', tools=[Tool(plain_tool, False)], retries=7)
    result = agent.run_sync('foobar')
    assert result.data == snapshot('{"plain_tool":1}')
    assert call_args == snapshot([0])
    assert agent._function_tools['plain_tool'].takes_ctx is False
    assert agent._function_tools['plain_tool'].max_retries == 7

    agent_infer = Agent('test', tools=[plain_tool], retries=7)
    result = agent_infer.run_sync('foobar')
    assert result.data == snapshot('{"plain_tool":1}')
    assert call_args == snapshot([0, 0])
    assert agent_infer._function_tools['plain_tool'].takes_ctx is False
    assert agent_infer._function_tools['plain_tool'].max_retries == 7


def ctx_tool(ctx: RunContext[int], x: int) -> int:
    return x + ctx.deps


# pyright: reportPrivateUsage=false
def test_init_tool_ctx(set_event_loop: None):
    agent = Agent('test', tools=[Tool(ctx_tool, True, max_retries=3)], deps_type=int, retries=7)
    result = agent.run_sync('foobar', deps=5)
    assert result.data == snapshot('{"ctx_tool":5}')
    assert agent._function_tools['ctx_tool'].takes_ctx is True
    assert agent._function_tools['ctx_tool'].max_retries == 3

    agent_infer = Agent('test', tools=[ctx_tool], deps_type=int)
    result = agent_infer.run_sync('foobar', deps=6)
    assert result.data == snapshot('{"ctx_tool":6}')
    assert agent_infer._function_tools['ctx_tool'].takes_ctx is True


def test_repeat_tool():
    with pytest.raises(UserError, match="Tool name conflicts with existing tool: 'ctx_tool'"):
        Agent('test', tools=[Tool(ctx_tool, True), ctx_tool], deps_type=int)


def test_tool_return_conflict():
    # this is okay
    Agent('test', tools=[ctx_tool], deps_type=int)
    # this is also okay
    Agent('test', tools=[ctx_tool], deps_type=int, result_type=int)
    # this raises an error
    with pytest.raises(UserError, match="Tool name conflicts with result schema name: 'ctx_tool'"):
        Agent('test', tools=[ctx_tool], deps_type=int, result_type=int, result_tool_name='ctx_tool')


def test_init_ctx_tool_invalid():
    def plain_tool(x: int) -> int:  # pragma: no cover
        return x + 1

    m = r'First parameter of tools that take context must be annotated with RunContext\[\.\.\.\]'
    with pytest.raises(UserError, match=m):
        Tool(plain_tool, True)


def test_init_plain_tool_invalid():
    with pytest.raises(UserError, match='RunContext annotations can only be used with tools that take context'):
        Tool(ctx_tool, False)


def test_return_pydantic_model(set_event_loop: None):
    agent = Agent('test')

    @agent.tool_plain
    def return_pydantic_model(x: int) -> Foo:
        return Foo(x=x, y='a')

    result = agent.run_sync('')
    assert result.data == snapshot('{"return_pydantic_model":{"x":0,"y":"a"}}')


def test_return_bytes(set_event_loop: None):
    agent = Agent('test')

    @agent.tool_plain
    def return_pydantic_model() -> bytes:
        return '🐈 Hello'.encode()

    result = agent.run_sync('')
    assert result.data == snapshot('{"return_pydantic_model":"🐈 Hello"}')


def test_return_bytes_invalid(set_event_loop: None):
    agent = Agent('test')

    @agent.tool_plain
    def return_pydantic_model() -> bytes:
        return b'\00 \x81'

    with pytest.raises(PydanticSerializationError, match='invalid utf-8 sequence of 1 bytes from index 2'):
        agent.run_sync('')


def test_return_unknown(set_event_loop: None):
    agent = Agent('test')

    class Foobar:
        pass

    @agent.tool_plain
    def return_pydantic_model() -> Foobar:
        return Foobar()

    with pytest.raises(PydanticSerializationError, match='Unable to serialize unknown type:'):
        agent.run_sync('')
