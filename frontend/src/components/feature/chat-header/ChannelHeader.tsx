import { PageHeader } from "@/components/layout/Heading/PageHeader"
import { ChannelIcon } from "@/utils/layout/channelIcon"
import { ChannelListItem } from "@/utils/channel/ChannelListProvider"
import { EditChannelNameButton } from "../channel-details/rename-channel/EditChannelNameButton"
import { Flex, Heading, Text } from "@radix-ui/themes"
import ChannelHeaderMenu from "./ChannelHeaderMenu"
import { ViewChannelMemberAvatars } from "./ViewChannelMemberAvatars"
import { BiChevronLeft } from "react-icons/bi"
import { Link } from "react-router-dom"
import { ViewPinnedMessagesButton } from "../pinned-messages/ViewPinnedMessagesButton"
import { useAtomValue } from "jotai"
import { lastWorkspaceAtom } from "@/utils/lastVisitedAtoms"
import { useContext, useMemo } from "react"
import { UserListContext } from "@/utils/users/UserListProvider"
import { UserAvatar } from "@/components/common/UserAvatar"
import { FaFacebook, FaLine } from "react-icons/fa"

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
    line: <FaLine className='text-[#06C755]' />,
    facebook: <FaFacebook className='text-[#1877F2]' />,
}

interface ChannelHeaderProps {
    channelData: ChannelListItem
}

export const ChannelHeader = ({ channelData }: ChannelHeaderProps) => {

    const lastWorkspace = useAtomValue(lastWorkspaceAtom)
    const { users } = useContext(UserListContext)

    const customerUser = useMemo(
        () => users.find(u => u.name === channelData.omni_channel_raven_user),
        [users, channelData.omni_channel_raven_user]
    )

    const isOmniChannel = !!channelData.omni_channel_raven_user
    const displayName = customerUser?.full_name ?? channelData.channel_name
    const providerIcon = channelData.omni_channel_provider ? PROVIDER_ICONS[channelData.omni_channel_provider] : null
    const providerDisplayName = channelData.omni_channel_display_name ?? channelData.omni_channel_chat_provider

    return (
        <PageHeader>
            <Flex align='center'>
                <Link to={`/${lastWorkspace}`} className="block bg-transparent hover:bg-transparent active:bg-transparent sm:hidden">
                    <BiChevronLeft size='24' className="block text-gray-12" />
                </Link>
                <Flex gap='4' align={'center'} className="group animate-fadein pr-4">
                    {isOmniChannel ? (
                        <Flex gap='2' align='center'>
                            <UserAvatar
                                src={customerUser?.user_image}
                                alt={displayName}
                                size='2'
                            />
                            <Heading
                                size={{ initial: '4', sm: '5' }}
                                className="mb-0.5 text-ellipsis line-clamp-1"
                            >
                                {displayName}
                            </Heading>
                            {providerDisplayName && (
                                <>
                                    <Text color='gray' size='4'>|</Text>
                                    {providerIcon && <span className='flex items-center text-base'>{providerIcon}</span>}
                                    <Text size='3' color='gray' className='text-ellipsis line-clamp-1'>{providerDisplayName}</Text>
                                </>
                            )}
                        </Flex>
                    ) : (
                        <Flex gap='1' align={'center'}>
                            <ChannelIcon type={channelData.type} size='18' />
                            <Heading
                                size={{
                                    initial: '4',
                                    sm: '5'
                                }}
                                className="mb-0.5 text-ellipsis line-clamp-1">{channelData.channel_name}</Heading>
                        </Flex>
                    )}
                    <EditChannelNameButton channelID={channelData.name} channel_name={channelData.channel_name} channelType={channelData.type} disabled={channelData.is_archived == 1} buttonVisible={!!channelData.pinned_messages_string} />
                    <ViewPinnedMessagesButton pinnedMessagesString={channelData.pinned_messages_string ?? ''} />
                </Flex>
            </Flex>

            <Flex gap='2' align='center' className="animate-fadein">
                <ViewChannelMemberAvatars channelData={channelData} />
                <ChannelHeaderMenu channelData={channelData} />
            </Flex>
        </PageHeader>
    )
}