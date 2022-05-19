from enum import Enum, unique
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Query, Path, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gazettes import GazetteAccessInterface, GazetteRequest
from suggestions import Suggestion, SuggestionServiceInterface
from companies import InvalidCNPJException, CompaniesAccessInterface
from config.config import load_configuration

config = load_configuration()

app = FastAPI(
    title="Querido Diário",
    description="API to access the gazettes from all Brazilian cities",
    version="0.12.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=config.cors_allow_methods,
    allow_headers=config.cors_allow_headers,
)


class GazetteItem(BaseModel):
    territory_id: str
    date: date
    url: str
    territory_name: str
    state_code: str
    highlight_texts: List[str]
    edition: Optional[str]
    is_extra_edition: Optional[bool]
    file_raw_txt: Optional[str]


class GazetteSearchResponse(BaseModel):
    total_gazettes: int
    gazettes: List[GazetteItem]


@unique
class CityLevel(str, Enum):
    ZERO = "0"
    ONE = "1"
    TWO = "2"
    THREE = "3"


class City(BaseModel):
    territory_id: str
    territory_name: str
    state_code: str
    publication_urls: Optional[List[str]]
    level: CityLevel


class CitiesSearchResponse(BaseModel):
    cities: List[City]


class CitySearchResponse(BaseModel):
    city: City


@unique
class SortBy(str, Enum):
    RELEVANCE = "relevance"
    DESCENDING_DATE = "descending_date"
    ASCENDING_DATE = "ascending_date"


class HTTPExceptionMessage(BaseModel):
    detail: str


class CreateSuggestionBody(BaseModel):
    email_address: str = Field(
        title="Email address", description="Email address who is sending email"
    )
    name: str = Field(
        title="Name", description="Name who is sending email",
    )
    content: str = Field(
        title="Email content", description="Email content with suggestion",
    )


class CreatedSuggestionResponse(BaseModel):
    status: str


class Company(BaseModel):
    cnpj_basico: str
    cnpj_ordem: str
    cnpj_dv: str
    cnpj_completo: str
    cnpj_completo_apenas_numeros: str
    identificador_matriz_filial: Optional[str]
    nome_fantasia: Optional[str]
    situacao_cadastral: Optional[str]
    data_situacao_cadastral: Optional[str]
    motivo_situacao_cadastral: Optional[str]
    nome_cidade_exterior: Optional[str]
    data_inicio_atividade: Optional[str]
    cnae_fiscal_secundario: Optional[str]
    tipo_logradouro: Optional[str]
    logradouro: Optional[str]
    numero: Optional[str]
    complemento: Optional[str]
    bairro: Optional[str]
    cep: Optional[str]
    uf: Optional[str]
    ddd_telefone_1: Optional[str]
    ddd_telefone_2: Optional[str]
    ddd_telefone_fax: Optional[str]
    correio_eletronico: Optional[str]
    situacao_especial: Optional[str]
    data_situacao_especial: Optional[str]
    pais: Optional[str]
    municipio: Optional[str]
    razao_social: Optional[str]
    natureza_juridica: Optional[str]
    qualificacao_do_responsavel: Optional[str]
    capital_social: Optional[str]
    porte: Optional[str]
    ente_federativo_responsavel: Optional[str]
    opcao_pelo_simples: Optional[str]
    data_opcao_pelo_simples: Optional[str]
    data_exclusao_pelo_simples: Optional[str]
    opcao_pelo_mei: Optional[str]
    data_opcao_pelo_mei: Optional[str]
    data_exclusao_pelo_mei: Optional[str]
    cnae: Optional[str]


class CompanySearchResponse(BaseModel):
    cnpj_info: Company


class Partner(BaseModel):
    cnpj_basico: str
    cnpj_ordem: str
    cnpj_dv: str
    cnpj_completo: str
    cnpj_completo_apenas_numeros: str
    identificador_socio: Optional[str]
    razao_social: Optional[str]
    cnpj_cpf_socio: Optional[str]
    qualificacao_socio: Optional[str]
    data_entrada_sociedade: Optional[str]
    pais_socio_estrangeiro: Optional[str]
    numero_cpf_representante_legal: Optional[str]
    nome_representante_legal: Optional[str]
    qualificacao_representante_legal: Optional[str]
    faixa_etaria: Optional[str]


class PartnersSearchResponse(BaseModel):
    total_partners: int
    partners: List[Partner]


def trigger_gazettes_search(
    territory_id: str = None,
    since: date = None,
    until: date = None,
    querystring: str = None,
    offset: int = 0,
    size: int = 10,
    fragment_size: int = 150,
    number_of_fragments: int = 1,
    pre_tags: List[str] = [""],
    post_tags: List[str] = [""],
    sort_by: SortBy = SortBy.RELEVANCE,
):
    gazettes_count, gazettes = app.gazettes.get_gazettes(
        GazetteRequest(
            territory_id,
            since=since,
            until=until,
            querystring=querystring,
            offset=offset,
            size=size,
            fragment_size=fragment_size,
            number_of_fragments=number_of_fragments,
            pre_tags=pre_tags,
            post_tags=post_tags,
            sort_by=sort_by.value,
        )
    )
    response = {
        "total_gazettes": 0,
        "gazettes": [],
    }
    if gazettes_count > 0 and gazettes:
        response["gazettes"] = gazettes
        response["total_gazettes"] = gazettes_count
    return response


@app.get(
    "/gazettes/",
    response_model=GazetteSearchResponse,
    name="Get gazettes",
    description="Get gazettes by date and keyword",
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def get_gazettes(
    since: Optional[date] = Query(
        None,
        title="Since date",
        description="YYYY-MM-DD. Look for gazettes where the date is greater or equal than given date ",
        # remove long description sin is not visible in swagger
    ),
    until: Optional[date] = Query(
        None,
        title="Until date",
        description="YYYY-MM-DD. Look for gazettes where the date is less or equal than given date",
        # remove long description sin is not visible in swagger
    ),
    querystring: Optional[str] = Query(
        None,
        title="Content should be present in the gazette according to querystring",
        description="Search for content in gazettes using ElasticSearch's 'simple query string syntax'",
    ),
    offset: Optional[int] = Query(
        0, title="Offset", description="Number of item to skip in the result search",
    ),
    size: Optional[int] = Query(
        10,
        title="Number of item to return",
        description="Define the number of item should be returned",
    ),
    fragment_size: Optional[int] = Query(
        150,
        title="Size of fragments (characters) of highlight to return.",
        description="Define the fragments (characters) of highlight of the item should be returned",
    ),
    number_of_fragments: Optional[int] = Query(
        1,
        title="Number of fragments (blocks) of highlight to return.",
        description="Define the number of fragments (blocks) of highlight should be returned",
    ),
    pre_tags: List[str] = Query(
        [""],
        title="Pre tags of fragments of highlight",
        description="Pre tags of fragments of highlight. This is a list of strings (usually HTML tags) that will appear before the text which matches the query",
    ),
    post_tags: List[str] = Query(
        [""],
        title="Post tags of fragments of highlight.",
        description="Post tags of fragments of highlight. This is a list of strings (usually HTML tags) that will appear after the text which matches the query",
    ),
    sort_by: Optional[SortBy] = Query(
        SortBy.RELEVANCE,
        title="Allow the user to define the order of the search results.",
        description="Allow the user to define the order of the search results. The API should allow 3 types: relevance, descending_date, ascending_date",
    ),
):
    return trigger_gazettes_search(
        None,
        since,
        until,
        querystring,
        offset,
        size,
        fragment_size,
        number_of_fragments,
        pre_tags,
        post_tags,
        sort_by,
    )


@app.get(
    "/gazettes/{territory_id}",
    response_model=GazetteSearchResponse,
    name="Get gazettes by territory ID",
    description="Get gazettes from specific city by date and querystring",
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def get_gazettes_by_territory_id(
    territory_id: str = Path(..., description="City's IBGE ID"),
    since: Optional[date] = Query(
        None,
        title="Since date",
        description="YYYY-MM-DD. Look for gazettes where the date is greater or equal than given date",
    ),
    until: Optional[date] = Query(
        None,
        title="Until date",
        description="YYYY-MM-DD. Look for gazettes where the date is less or equal than given date",
    ),
    querystring: Optional[str] = Query(
        None,
        title="Content should be present in the gazette according to querystring",
        description="Search for content in gazettes using ElasticSearch's 'simple query string syntax'",
    ),
    offset: Optional[int] = Query(
        0, title="Offset", description="Number of item to skip in the result search",
    ),
    size: Optional[int] = Query(
        10,
        title="Number of item to return",
        description="Define the number of item should be returned",
    ),
    fragment_size: Optional[int] = Query(
        150,
        title="Size of fragments (characters) of highlight to return.",
        description="Define the fragments (characters)  of highlight of the item should be returned",
    ),
    number_of_fragments: Optional[int] = Query(
        1,
        title="Number of fragments (blocks) of highlight to return.",
        description="Define the number of fragments (blocks) of highlight should be returned",
    ),
    pre_tags: List[str] = Query(
        [""],
        title="Pre tags of fragments of highlight",
        description="Pre tags of fragments of highlight. This is a list of strings (usually HTML tags) that will appear before the text which matches the query",
    ),
    post_tags: List[str] = Query(
        [""],
        title="Post tags of fragments of highlight.",
        description="Post tags of fragments of highlight. This is a list of strings (usually HTML tags) that will appear after the text which matches the query",
    ),
    sort_by: Optional[SortBy] = Query(
        SortBy.RELEVANCE,
        title="Allow the user to define the order of the search results.",
        description="Allow the user to define the order of the search results. The API should allow 3 types: relevance, descending_date, ascending_date",
    ),
):
    return trigger_gazettes_search(
        territory_id,
        since,
        until,
        querystring,
        offset,
        size,
        fragment_size,
        number_of_fragments,
        pre_tags,
        post_tags,
        sort_by,
    )


@app.get(
    "/cities/",
    response_model=CitiesSearchResponse,
    name="Search for cities with name similar to the city_name query.",
    description="Search for cities with name similar to the city_name query.",
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def get_cities(city_name: str):
    cities = app.gazettes.get_cities(city_name)
    return {"cities": cities}


@app.get(
    "/cities/{territory_id}",
    response_model=CitySearchResponse,
    name="Get city by territory ID",
    description="Get general info from specific city by territory 7-digit IBGE ID.",
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
    responses={
        404: {"model": HTTPExceptionMessage, "description": "City can't be found"}
    },
)
async def get_city(territory_id: str = Path(..., description="City's IBGE ID")):
    city_info = app.gazettes.get_city(territory_id)
    if city_info is None:
        return JSONResponse(status_code=404, content={"detail": "City not found."})
    return {"city": city_info}


@app.post(
    "/suggestions",
    response_model=CreatedSuggestionResponse,
    name="Send a suggestion",
    description="Send a suggestion to the project",
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
async def add_suggestion(response: Response, body: CreateSuggestionBody):
    suggestion = Suggestion(
        email_address=body.email_address, name=body.name, content=body.content,
    )
    suggestion_sent = app.suggestion_service.add_suggestion(suggestion)
    response.status_code = (
        status.HTTP_200_OK if suggestion_sent.success else status.HTTP_400_BAD_REQUEST
    )
    return {"status": suggestion_sent.status}


@app.get(
    "/company/info/{cnpj:path}",
    response_model=CompanySearchResponse,
    name="Get company info by CNPJ number",
    description="Get info from specific company by its CNPJ number.",
    responses={
        404: {"model": HTTPExceptionMessage, "description": "Company can't be found"},
        400: {"model": HTTPExceptionMessage, "description": "CNPJ is not valid"},
    },
)
async def get_company(cnpj: str = Path(..., description="Company's CNPJ number")):
    try:
        company_info = app.companies.get_company(cnpj)
    except InvalidCNPJException as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    if company_info is None:
        return JSONResponse(status_code=404, content={"detail": "Company not found."})

    return {"cnpj_info": company_info}


@app.get(
    "/company/partners/{cnpj:path}",
    response_model=PartnersSearchResponse,
    name="Get company's partners infos by CNPJ number",
    description="Get info of partners of a company by its CNPJ number.",
    responses={
        400: {"model": HTTPExceptionMessage, "description": "CNPJ is not valid"},
    },
)
async def get_partners(cnpj: str = Path(..., description="Company's CNPJ number")):
    try:
        total_partners, partners = app.companies.get_partners(cnpj)
    except InvalidCNPJException as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return {"total_partners": total_partners, "partners": partners}


def configure_api_app(
    gazettes: GazetteAccessInterface,
    suggestion_service: SuggestionServiceInterface,
    companies: CompaniesAccessInterface,
    api_root_path=None,
):
    if not isinstance(gazettes, GazetteAccessInterface):
        raise Exception(
            "Only GazetteAccessInterface object are accepted for gazettes parameter"
        )
    if not isinstance(suggestion_service, SuggestionServiceInterface):
        raise Exception(
            "Only SuggestionServiceInterface object are accepted for suggestion_service parameter"
        )
    if not isinstance(companies, CompaniesAccessInterface):
        raise Exception(
            "Only CompaniesAccessInterface object are accepted for companies parameter"
        )
    if api_root_path is not None and type(api_root_path) != str:
        raise Exception("Invalid api_root_path")
    app.gazettes = gazettes
    app.suggestion_service = suggestion_service
    app.companies = companies
    app.root_path = api_root_path
