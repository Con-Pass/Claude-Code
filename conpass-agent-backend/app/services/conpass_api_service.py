from app.core.config import settings
from typing import List, Optional, Any, Dict
from urllib.parse import unquote
import httpx
from app.core.logging_config import get_logger
from app.schemas.general import GeneralResponse

logger = get_logger(__name__)


class ConpassApiService:
    def __init__(self, conpass_jwt: str):
        self.conpass_base_url = settings.CONPASS_API_BASE_URL
        self.conpass_cookie = f"auth-token={conpass_jwt};"
        self.conpass_jwt = conpass_jwt

    def _map_number_of_contracts_to_cookie(self, number_of_contracts: int) -> str:
        if number_of_contracts < 1:
            number_of_contracts = 1
        if number_of_contracts > 100:
            number_of_contracts = 100
        return f"contract-search-setting=pageSize:{number_of_contracts};"

    async def _get_data_from_conpass_api(
        self, path: str, params: dict, number_of_contracts: int | None = None
    ) -> GeneralResponse:
        try:
            cookie = self.conpass_cookie
            if number_of_contracts:
                cookie = cookie + self._map_number_of_contracts_to_cookie(
                    number_of_contracts
                )

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    self.conpass_base_url + path,
                    headers={"Cookie": cookie},
                    params=params,
                )

            return GeneralResponse(
                status="success",
                description="Data fetched from ConPass API successfully",
                data=response.json(),
            )
        except Exception:
            logger.exception(
                f"Error fetching data from ConPass API: {path}, {params}, {number_of_contracts}"
            )
            return GeneralResponse(
                status="error", description="Error fetching data from ConPass API"
            )

    async def _put_data_to_conpass_api(
        self, path: str, json_data: dict
    ) -> GeneralResponse:
        """
        Send PUT request to ConPass API.

        Args:
            path: API endpoint path
            json_data: JSON payload for the request

        Returns:
            GeneralResponse with status and data
        """
        try:
            cookie = self.conpass_cookie

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.put(
                    self.conpass_base_url + path,
                    headers={"Cookie": cookie, "Content-Type": "application/json"},
                    json=json_data,
                )

            if response.status_code >= 400:
                logger.error(
                    f"ConPass API PUT error: {path}, status={response.status_code}, response={response.text}"
                )
                return GeneralResponse(
                    status="error",
                    description=f"ConPass API error: {response.status_code}",
                    data=response.json() if response.text else None,
                )

            return GeneralResponse(
                status="success",
                description="Data sent to ConPass API successfully",
                data=response.json() if response.text else None,
            )
        except httpx.TimeoutException:
            logger.exception(f"Timeout sending data to ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Request timeout to ConPass API"
            )
        except Exception:
            logger.exception(f"Error sending data to ConPass API: {path}, {json_data}")
            return GeneralResponse(
                status="error", description="Error sending data to ConPass API"
            )

    async def _post_data_to_conpass_api(
        self, path: str, json_data: dict
    ) -> GeneralResponse:
        """
        Send POST request to ConPass API.

        Args:
            path: API endpoint path
            json_data: JSON payload for the request

        Returns:
            GeneralResponse with status and data
        """
        try:
            cookie = self.conpass_cookie

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.post(
                    self.conpass_base_url + path,
                    headers={"Cookie": cookie, "Content-Type": "application/json"},
                    json=json_data,
                )

            if response.status_code >= 400:
                logger.error(
                    f"ConPass API POST error: {path}, status={response.status_code}, response={response.text}"
                )
                return GeneralResponse(
                    status="error",
                    description=f"ConPass API error: {response.status_code}",
                    data=response.json() if response.text else None,
                )

            return GeneralResponse(
                status="success",
                description="Data sent to ConPass API successfully",
                data=response.json() if response.text else None,
            )
        except httpx.TimeoutException:
            logger.exception(f"Timeout sending data to ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Request timeout to ConPass API"
            )
        except Exception:
            logger.exception(f"Error sending data to ConPass API: {path}, {json_data}")
            return GeneralResponse(
                status="error", description="Error sending data to ConPass API"
            )

    async def _delete_data_from_conpass_api(self, path: str) -> GeneralResponse:
        """
        Send DELETE request to ConPass API.

        Args:
            path: API endpoint path

        Returns:
            GeneralResponse with status and data
        """
        try:
            cookie = self.conpass_cookie

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.delete(
                    self.conpass_base_url + path,
                    headers={"Cookie": cookie},
                )

            if response.status_code >= 400:
                logger.error(
                    f"ConPass API DELETE error: {path}, status={response.status_code}, response={response.text}"
                )
                return GeneralResponse(
                    status="error",
                    description=f"ConPass API error: {response.status_code}",
                    data=response.json() if response.text else None,
                )

            return GeneralResponse(
                status="success",
                description="Data deleted from ConPass API successfully",
                data=response.json() if response.text else None,
            )
        except httpx.TimeoutException:
            logger.exception(f"Timeout deleting data from ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Request timeout to ConPass API"
            )
        except Exception:
            logger.exception(f"Error deleting data from ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Error deleting data from ConPass API"
            )

    async def _delete_global_metadata_key_from_conpass_api(
            self, path: str, json_data: dict
    ) -> GeneralResponse:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.request(
                    method="DELETE",
                    url=f"{self.conpass_base_url}{path}",
                    headers={
                        "Authorization": f"JWT {self.conpass_jwt}",
                        "Cookie": self.conpass_cookie,
                        "Content-Type": "application/json",
                    },
                    json=json_data,
                )

            if response.status_code >= 400:
                logger.error(
                    f"ConPass API DELETE error: {path}, "
                    f"status={response.status_code}, response={response.text}"
                )
                return GeneralResponse(
                    status="error",
                    description=f"ConPass API error: {response.status_code}",
                    data=response.json() if response.text else None,
                )

            # ✅ SUCCESS CASE
            return GeneralResponse(
                status="success",
                description="Data deleted from ConPass API successfully",
                data=response.json() if response.text else None,
            )

        except httpx.TimeoutException:
            logger.exception(f"Timeout deleting data from ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Request timeout to ConPass API"
            )
        except Exception:
            logger.exception(f"Error deleting data from ConPass API: {path}")
            return GeneralResponse(
                status="error", description="Error deleting data from ConPass API"
            )

    async def get_contract_metadata(self, contract_id: int) -> GeneralResponse:
        path = f"/contract/{contract_id}/metadata"
        return await self._get_data_from_conpass_api(path, {})

    async def get_contract(
        self, contract_id: int, contract_type: int = 1
    ) -> GeneralResponse:
        """
        Get contract information including directory ID.

        Args:
            contract_id: The ID of the contract
            contract_type: Contract type (1 = normal contract, 2 = template). Defaults to 1.

        Returns:
            GeneralResponse with contract information including directory.id
        """
        path = "/contract"
        params = {"id": contract_id, "type": contract_type}
        logger.info(
            f"Fetching contract information for contract {contract_id} (type={contract_type})"
        )
        return await self._get_data_from_conpass_api(path, params)

    async def get_contracts(
        self, params: dict, number_of_contracts: int | None = None
    ) -> GeneralResponse:
        path = "/contract/paginate"
        return await self._get_data_from_conpass_api(path, params, number_of_contracts)

    async def get_contract_body(self, contract_id: int) -> GeneralResponse:
        path = "/contract/body/list"
        params = {"id": contract_id}
        return await self._get_data_from_conpass_api(path, params)

    async def get_directory_metadata_settings(
        self, directory_id: int
    ) -> GeneralResponse:
        """
        Fetch metadata visibility settings for a directory.

        Args:
            directory_id: Directory ID to inspect

        Returns:
            GeneralResponse with directory metadata configuration
        """
        path = "/setting/directory/meta"
        params = {"id": str(directory_id)}
        logger.info(
            f"Fetching directory metadata settings for directory {directory_id}"
        )
        return await self._get_data_from_conpass_api(path, params)

    async def get_contract_body_text(self, contract_id: int) -> Optional[str]:
        """
        Fetch contract body text from ConPass API and return decoded plain text.

        Uses the /contract/body/list endpoint (documented in CONPASS_BODY_API_DOCUMENTATION.md)
        to retrieve the contract text directly. Returns the latest version (first item in list).

        Args:
            contract_id: The contract ID to fetch

        Returns:
            Decoded contract body text as string, or None if not found or on error

        Note:
            This method is specifically for agent tools that need contract text.
            It handles response parsing and URL decoding automatically.
        """
        try:
            path = "/contract/body/list"
            params = {"id": contract_id}

            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(
                    self.conpass_base_url + path,
                    headers={"Cookie": self.conpass_cookie},
                    params=params,
                )
                response.raise_for_status()

                data = response.json()

                # Parse response format: {"response": [{"diff": "...", "body": {"body": "..."}}, ...]}
                # List is ordered newest first, so we take the first item
                if isinstance(data, dict) and "response" in data:
                    response_list = data["response"]
                    if isinstance(response_list, list) and len(response_list) > 0:
                        first_item = response_list[0]
                        if isinstance(first_item, dict) and "body" in first_item:
                            body_obj = first_item["body"]
                            if isinstance(body_obj, dict) and "body" in body_obj:
                                body_text = body_obj["body"]
                                # URL decode the body text
                                decoded_text = unquote(body_text) if body_text else ""
                                return decoded_text

                logger.warning(
                    f"Unexpected response format from /contract/body/list for contract {contract_id}"
                )
                return None

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching contract body for {contract_id}: {e.response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Error fetching contract body text for contract {contract_id}: {e}"
            )
            return None

    async def get_allowed_directories(self) -> List[int]:
        """
        Fetch allowed directories from ConPass API and return only the directory IDs.

        Returns:
            List of directory IDs.
        """
        path = "/setting/directory/list/allowed"
        params = {}  # type: ignore
        response = await self._get_data_from_conpass_api(path, params)

        # Extract directory IDs from response data
        if response.status == "success" and response.data:
            try:
                # API returns: {"response": [{"id": 211, "name": "...", ...}, ...]}
                directories_data = response.data
                directory_list = None

                if (
                    isinstance(directories_data, dict)
                    and "response" in directories_data
                ):
                    # Response is wrapped in a dict with 'response' key
                    directory_list = directories_data.get("response", [])
                elif isinstance(directories_data, list):
                    # Response is directly a list
                    directory_list = directories_data
                else:
                    logger.warning(
                        f"Unexpected response format from allowed directories API: {type(directories_data)}"
                    )
                    return []

                # Extract IDs from directory objects
                if isinstance(directory_list, list):
                    directory_ids = [
                        directory.get("id")
                        for directory in directory_list
                        if isinstance(directory, dict) and "id" in directory
                    ]
                    return directory_ids
                else:
                    logger.warning(
                        f"Expected list of directories but got: {type(directory_list)}"
                    )
                    return []
            except Exception as e:
                logger.exception(
                    f"Error parsing allowed directories response: {e}",
                    exc_info=True,
                )
                return []

        return []

    async def get_allowed_directories_with_names(self) -> List[Dict[str, Any]]:
        """
        Fetch allowed directories from ConPass API and return the dict containing directory IDs and Names.

        Returns:
            List of dict containing directory IDs and Names.
        """
        path = "/setting/directory/list/allowed"
        params = {}  # type: ignore
        response = await self._get_data_from_conpass_api(path, params)

        # Extract directory IDs from response data
        if response.status == "success" and response.data:
            try:
                # API returns: {"response": [{"id": 211, "name": "...", ...}, ...]}
                directories_data = response.data
                directory_list = None

                if (
                    isinstance(directories_data, dict)
                    and "response" in directories_data
                ):
                    # Response is wrapped in a dict with 'response' key
                    directory_list = directories_data.get("response", [])
                elif isinstance(directories_data, list):
                    # Response is directly a list
                    directory_list = directories_data
                else:
                    logger.warning(
                        f"Unexpected response format from allowed directories API: {type(directories_data)}"
                    )
                    return []

                if isinstance(directory_list, list):
                    directory_ids = [
                        {
                            "directory_id": directory.get("id"),
                            "directory_name": directory.get("name")
                        }

                        for directory in directory_list
                        if isinstance(directory, dict) and "id" in directory and "name" in directory
                    ]
                    return directory_ids
                else:
                    logger.warning(
                        f"Expected list of directories but got: {type(directory_list)}"
                    )
                    return []
            except Exception as e:
                logger.exception(
                    f"Error parsing allowed directories response: {e}",
                    exc_info=True,
                )
                return []

        return []

    async def create_contract_metadata(
        self, contract_id: int, params: dict
    ) -> GeneralResponse:
        """
        Create metadata for a contract using PUT /contract/{contract_id}/metadata.

        Args:
            contract_id: The ID of the contract
            params: Dictionary with 'list' key containing metadata items to create

        Returns:
            GeneralResponse with status and created metadata
        """
        path = f"/contract/{contract_id}/metadata"
        logger.info(f"Creating metadata for contract {contract_id}: {params}")
        return await self._put_data_to_conpass_api(path, {"params": params})

    async def update_contract_metadata(
        self, contract_id: int, params: dict
    ) -> GeneralResponse:
        """
        Update metadata for a contract using PUT /contract/{contract_id}/metadata.

        Args:
            contract_id: The ID of the contract
            params: Dictionary with 'list' key containing metadata items to update

        Returns:
            GeneralResponse with status and updated metadata
        """
        path = f"/contract/{contract_id}/metadata"
        logger.info(f"Updating metadata for contract {contract_id}: {params}")
        return await self._put_data_to_conpass_api(path, {"params": params})

    async def delete_contract_metadata(self, metadata_id: int) -> GeneralResponse:
        """
        Delete metadata using DELETE /contract/metadata/{metadata_id}.

        Args:
            metadata_id: The ID of the metadata record to delete

        Returns:
            GeneralResponse with status
        """
        path = f"/contract/metadata/{metadata_id}"
        logger.info(f"Deleting metadata {metadata_id}")
        return await self._delete_data_from_conpass_api(path)

    async def get_free_metadata_keys(self) -> GeneralResponse:
        """
        Get available FREE (custom) metadata keys for the current user's account.

        Returns:
            GeneralResponse with list of FREE metadata keys
        """
        path = "/contract/metakey/free"
        return await self._get_data_from_conpass_api(path, {})

    async def get_all_metadata_keys(self) -> GeneralResponse:
        """
        Get all metadata keys (both DEFAULT and FREE) available for the current account.

        Returns:
            GeneralResponse with list of all metadata keys including their visibility settings
        """
        path = "/setting/meta"
        logger.info("Fetching all metadata keys (DEFAULT and FREE) for account")
        return await self._get_data_from_conpass_api(path, {})

    async def create_meta_key(self, names: List[str], is_visible: bool = True) -> GeneralResponse:
        """
        Create a new FREE MetaKey using POST /setting/meta/update.

        Args:
            names: Display name for the metadata key (max 255 characters)
            is_visible: Account-level visibility setting

        Returns:
            GeneralResponse with status and creation result
        """
        path = "/setting/free-meta-key"
        payload = {
            "keys": names
        }
        logger.info(
            f"Creating FREE MetaKey with name='{names}', is_visible={is_visible}"
        )
        return await self._post_data_to_conpass_api(path, payload)

    async def update_meta_key(
        self,
        key_id: int,
        name: str,
        is_visible: bool,
        key_type: int = 2,
        status: int = 1,
    ) -> GeneralResponse:
        """
        Update an existing MetaKey using POST /setting/meta/update.

        Args:
            key_id: The ID of the metadata key to update
            name: Updated display name for the metadata key (max 255 characters)
            is_visible: Account-level visibility setting
            key_type: Metadata key type (2 = FREE/custom). Defaults to 2.
            status: Status (1 = ENABLE). Defaults to 1.

        Returns:
            GeneralResponse with status and update result
        """
        path = "/setting/meta/update"
        payload = {
            "settingMeta": [
                {
                    "id": key_id,  # Existing key ID for update
                    "name": name,
                    "type": key_type,
                    "is_visible": is_visible,
                    "status": status,
                }
            ]
        }
        logger.info(
            f"Updating MetaKey id={key_id} with name='{name}', is_visible={is_visible}, type={key_type}, status={status}"
        )
        return await self._post_data_to_conpass_api(path, payload)

    async def delete_meta_key(self, key_ids: List[int]) -> GeneralResponse:
        """
        Delete a FREE MetaKey using POST /setting/meta/update with status=0.

        Args:
            key_ids: List of FREE metadata key IDs to delete

        Returns:
            GeneralResponse with status and deletion result
        """
        path = "/setting/free-meta-key"
        payload = {
            "ids": key_ids
        }
        logger.info(f"Deleting FREE MetaKey with key_ids={key_ids}")
        return await self._delete_global_metadata_key_from_conpass_api(path, payload)

    async def configure_directory_metadata(
        self, directory_id: int, default_list: list, free_list: list
    ) -> GeneralResponse:
        """
        Configure directory metadata settings using POST /setting/directory/meta/update.

        Associates MetaKeys with directories and sets directory-level visibility.

        Args:
            directory_id: Directory ID to configure
            default_list: List of DEFAULT metadata key configurations
            free_list: List of FREE metadata key configurations

        Returns:
            GeneralResponse with status and configuration result
        """
        path = "/setting/directory/meta/update"
        payload = {
            "directoryId": str(directory_id),
            "defaultList": default_list,
            "freeList": free_list,
        }
        logger.info(
            f"Configuring directory {directory_id} metadata: "
            f"{len(default_list)} default keys, {len(free_list)} free keys"
        )
        return await self._post_data_to_conpass_api(path, payload)

    async def get_user_list(self) -> GeneralResponse:
        """
        Get list of available users from /user/list using POST method.

        Args:
            user_name: Optional filter by username (partial match) - currently not used in payload

        Returns:
            GeneralResponse with list of users (each user has id, loginName, username, email, type, status)
        """
        path = "/user/data/list"
        payload: dict[str, Any] = {}
        logger.info("Fetching user list")
        return await self._post_data_to_conpass_api(path, payload)


def get_conpass_api_service(conpass_jwt: str) -> ConpassApiService:
    return ConpassApiService(conpass_jwt=conpass_jwt)
